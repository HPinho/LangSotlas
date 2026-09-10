/* Sotlas Native Toolchain Driver */
#define _CRT_SECURE_NO_WARNINGS
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <stdbool.h>
#include <time.h>

#if defined(_WIN32)
#include <windows.h>
#include <io.h>
#include <direct.h>
#ifndef ENABLE_VIRTUAL_TERMINAL_PROCESSING
#define ENABLE_VIRTUAL_TERMINAL_PROCESSING 0x0004
#endif
#else
#include <dirent.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

#define MAX_SOURCE_SIZE (8 * 1024 * 1024) // 8 MB
#define MAX_OUTPUT_SIZE (16 * 1024 * 1024) // 16 MB

// Função exportada do compilador Sotlas auto-hospedado
size_t sotlas_compile(const uint8_t *source, uint8_t *out_buf, size_t max_len);

static void print_usage(const char *prog_name) {
    printf("sotlas 1.0.0-dev (x86_64-pc-windows-msvc)\n\n");
    printf("Usage:\n");
    printf("  %s <file.sotlas ...> [-o <out.exe|out.c>]\n", prog_name);
    printf("  %s run <file.sotlas> [-- args...]\n", prog_name);
    printf("  %s test [dir_or_file.sotlas ...] [-v|--verbose]\n", prog_name);
    printf("  %s fmt [file_or_dir] [--check]\n", prog_name);
    printf("  %s lint [file_or_dir]\n", prog_name);
    printf("  %s build [--path <dir>] [-o <out>]\n", prog_name);
    printf("  %s init [--lib]\n", prog_name);
    printf("  %s new <project_name> [--lib]\n", prog_name);
    printf("  %s add <dependency> [--version <ver>] [--path <dir>]\n", prog_name);
    printf("  %s compile <file.sotlas ...> [-o <out.exe|out.c>]\n", prog_name);
    printf("  %s --version\n", prog_name);
}

static const char* find_c_compiler(void) {
    const char *env_clang = getenv("CLANG_PATH");
    if (env_clang && env_clang[0] != 0) return env_clang;

#if defined(_WIN32)
    static const char *candidates[] = {
        "clang.exe",
        "C:\\Program Files\\LLVM\\bin\\clang.exe",
        "gcc.exe"
    };
    for (size_t i = 0; i < sizeof(candidates)/sizeof(candidates[0]); i++) {
        char cmd[512];
        snprintf(cmd, sizeof(cmd), "\"\"%s\" --version >nul 2>&1\"", candidates[i]);
        if (system(cmd) == 0) {
            return candidates[i];
        }
    }
    return "clang.exe";
#else
    return "clang";
#endif
}

static bool ends_with(const char *str, const char *suffix) {
    if (!str || !suffix) return false;
    size_t len_str = strlen(str);
    size_t len_suf = strlen(suffix);
    if (len_str < len_suf) return false;
    return strcmp(str + (len_str - len_suf), suffix) == 0;
}

static bool is_directory(const char *path) {
#if defined(_WIN32)
    DWORD attrs = GetFileAttributesA(path);
    return (attrs != INVALID_FILE_ATTRIBUTES && (attrs & FILE_ATTRIBUTE_DIRECTORY));
#else
    struct stat st;
    if (stat(path, &st) != 0) return false;
    return S_ISDIR(st.st_mode);
#endif
}

static bool file_exists(const char *path) {
    FILE *f = fopen(path, "rb");
    if (f) {
        fclose(f);
        return true;
    }
    return false;
}

static void make_dir(const char *path) {
#if defined(_WIN32)
    CreateDirectoryA(path, NULL);
#else
    mkdir(path, 0755);
#endif
}

static void make_dir_recursive(const char *path) {
    char temp[512];
    strncpy(temp, path, 511);
    temp[511] = 0;
    for (char *p = temp; *p; p++) {
        if (*p == '/' || *p == '\\') {
            char orig = *p;
            *p = 0;
            if (temp[0] && strcmp(temp, ".") != 0) {
                make_dir(temp);
            }
            *p = orig;
        }
    }
    make_dir(temp);
}

#define MAX_LOADED_FILES 256
static char g_loaded_files[MAX_LOADED_FILES][512];
static int g_num_loaded_files = 0;

static bool is_file_loaded(const char *path) {
    for (int i = 0; i < g_num_loaded_files; i++) {
        if (strcmp(g_loaded_files[i], path) == 0) return true;
    }
    return false;
}

static void mark_file_loaded(const char *path) {
    if (g_num_loaded_files < MAX_LOADED_FILES) {
        strncpy(g_loaded_files[g_num_loaded_files++], path, 511);
    }
}

static void get_dir_of_file(const char *file_path, char *dir_buf, size_t max_len) {
    strncpy(dir_buf, file_path, max_len - 1);
    dir_buf[max_len - 1] = 0;
    char *last_slash = strrchr(dir_buf, '/');
    char *last_bslash = strrchr(dir_buf, '\\');
    char *s = (last_slash > last_bslash) ? last_slash : last_bslash;
    if (s) {
        *s = 0;
    } else {
        strcpy(dir_buf, ".");
    }
}

static bool try_resolve_and_load(const char *base_dir, const char *imp_path, uint8_t *dest, size_t *pos, size_t max_size);

static bool load_source_file(const char *path, uint8_t *dest, size_t *pos, size_t max_size) {
    if (is_file_loaded(path)) return true;

    FILE *f = fopen(path, "rb");
    if (!f) return false;

    fseek(f, 0, SEEK_END);
    long fsize = ftell(f);
    fseek(f, 0, SEEK_SET);
    if (fsize <= 0) {
        fclose(f);
        mark_file_loaded(path);
        return true;
    }

    char *buf = (char *)malloc(fsize + 1);
    if (!buf) { fclose(f); return false; }
    size_t rd = fread(buf, 1, fsize, f);
    buf[rd] = 0;
    fclose(f);

    mark_file_loaded(path);

    char dir[512];
    get_dir_of_file(path, dir, sizeof(dir));

    char *p = buf;
    while ((p = strstr(p, "import ")) != NULL) {
        p += 7;
        while (*p == ' ' || *p == '\t') p++;
        char imp_name[128];
        size_t k = 0;
        while (*p && *p != ';' && *p != ' ' && *p != '\t' && *p != '\n' && *p != '\r' && k < 127) {
            imp_name[k++] = *p++;
        }
        imp_name[k] = 0;
        if (k >= 3 && strcmp(imp_name + k - 3, "::*") == 0) {
            imp_name[k - 3] = 0;
        }
        if (imp_name[0]) {
            try_resolve_and_load(dir, imp_name, dest, pos, max_size);
        }
    }

    if (*pos + rd + 2 < max_size) {
        memcpy(dest + *pos, buf, rd);
        *pos += rd;
        dest[*pos] = '\n';
        *pos += 1;
        dest[*pos] = 0;
    }
    free(buf);
    return true;
}

static bool try_resolve_and_load(const char *base_dir, const char *imp_path, uint8_t *dest, size_t *pos, size_t max_size) {
    char rel_path[256];
    strncpy(rel_path, imp_path, 255);
    rel_path[255] = 0;
    for (char *c = rel_path; *c; c++) {
        if (*c == ':' && *(c+1) == ':') {
            *c = '/';
            memmove(c + 1, c + 2, strlen(c + 2) + 1);
        }
    }
    const char *last_part = strrchr(rel_path, '/');
    const char *leaf = last_part ? (last_part + 1) : rel_path;

    char candidates[16][512];
    int num_candidates = 0;
    snprintf(candidates[num_candidates++], sizeof(candidates[0]), "%s/%s.sotlas", base_dir, rel_path);
    snprintf(candidates[num_candidates++], sizeof(candidates[0]), "%s/%s.sotlas", base_dir, leaf);
    snprintf(candidates[num_candidates++], sizeof(candidates[0]), "%s/../%s.sotlas", base_dir, rel_path);
    snprintf(candidates[num_candidates++], sizeof(candidates[0]), "%s/../%s.sotlas", base_dir, leaf);
    snprintf(candidates[num_candidates++], sizeof(candidates[0]), "%s/../../stdlib/%s.sotlas", base_dir, rel_path);
    snprintf(candidates[num_candidates++], sizeof(candidates[0]), "%s/../../bootstrap/sotlas/%s.sotlas", base_dir, rel_path);
    snprintf(candidates[num_candidates++], sizeof(candidates[0]), "%s/../../../stdlib/%s.sotlas", base_dir, rel_path);
    snprintf(candidates[num_candidates++], sizeof(candidates[0]), "stdlib/%s.sotlas", rel_path);
    snprintf(candidates[num_candidates++], sizeof(candidates[0]), "stdlib/foundation/%s.sotlas", leaf);
    snprintf(candidates[num_candidates++], sizeof(candidates[0]), "stdlib/system/%s.sotlas", leaf);
    snprintf(candidates[num_candidates++], sizeof(candidates[0]), "bootstrap/sotlas/%s.sotlas", rel_path);
    snprintf(candidates[num_candidates++], sizeof(candidates[0]), "bootstrap/sotlas/sotlas_lite/%s.sotlas", rel_path);

    for (int i = 0; i < num_candidates; i++) {
        FILE *tf = fopen(candidates[i], "rb");
        if (tf) {
            fclose(tf);
            return load_source_file(candidates[i], dest, pos, max_size);
        }
    }
    return false;
}

#define MAX_TEST_FILES 512
static char g_test_files[MAX_TEST_FILES][512];
static int g_test_file_count = 0;

static void add_test_file(const char *path) {
    if (g_test_file_count >= MAX_TEST_FILES) return;
    for (int i = 0; i < g_test_file_count; i++) {
        if (strcmp(g_test_files[i], path) == 0) return;
    }
    strncpy(g_test_files[g_test_file_count++], path, 511);
}

static void scan_test_dir(const char *dir_path) {
#if defined(_WIN32)
    char search_pattern[512];
    snprintf(search_pattern, sizeof(search_pattern), "%s/*", dir_path);
    WIN32_FIND_DATAA fd;
    HANDLE h = FindFirstFileA(search_pattern, &fd);
    if (h == INVALID_HANDLE_VALUE) return;
    do {
        if (strcmp(fd.cFileName, ".") == 0 || strcmp(fd.cFileName, "..") == 0) continue;
        char full_path[512];
        snprintf(full_path, sizeof(full_path), "%s/%s", dir_path, fd.cFileName);
        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            scan_test_dir(full_path);
        } else if (ends_with(fd.cFileName, ".sotlas")) {
            add_test_file(full_path);
        }
    } while (FindNextFileA(h, &fd));
    FindClose(h);
#else
    DIR *d = opendir(dir_path);
    if (!d) return;
    struct dirent *entry;
    while ((entry = readdir(d)) != NULL) {
        if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0) continue;
        char full_path[512];
        snprintf(full_path, sizeof(full_path), "%s/%s", dir_path, entry->d_name);
        struct stat st;
        if (stat(full_path, &st) == 0) {
            if (S_ISDIR(st.st_mode)) {
                scan_test_dir(full_path);
            } else if (ends_with(entry->d_name, ".sotlas")) {
                add_test_file(full_path);
            }
        }
    }
    closedir(d);
#endif
}

static int run_test_command(int argc, char **argv) {
    bool verbose = false;
    #define MAX_CMD_ARGS 64
    int path_args[MAX_CMD_ARGS];
    int num_path_args = 0;

    for (int i = 2; i < argc; i++) {
        if (strcmp(argv[i], "-v") == 0 || strcmp(argv[i], "--verbose") == 0) {
            verbose = true;
        } else if (argv[i][0] != '-') {
            if (num_path_args < MAX_CMD_ARGS) {
                path_args[num_path_args++] = i;
            }
        }
    }

    g_test_file_count = 0;

    if (num_path_args == 0) {
        if (is_directory("tests/native")) {
            scan_test_dir("tests/native");
        } else if (is_directory("tests")) {
            scan_test_dir("tests");
        } else {
            scan_test_dir(".");
        }
    } else {
        for (int i = 0; i < num_path_args; i++) {
            const char *p = argv[path_args[i]];
            if (is_directory(p)) {
                scan_test_dir(p);
            } else if (file_exists(p) && ends_with(p, ".sotlas")) {
                add_test_file(p);
            } else {
                char with_ext[512];
                snprintf(with_ext, sizeof(with_ext), "%s.sotlas", p);
                if (file_exists(with_ext)) {
                    add_test_file(with_ext);
                } else {
                    fprintf(stderr, "sotlas-test: caminho nao encontrado: %s\n", p);
                }
            }
        }
    }

    if (g_test_file_count == 0) {
        fprintf(stderr, "sotlas-test: nenhum arquivo de teste (.sotlas) encontrado.\n");
        return 1;
    }

    const char *cc = find_c_compiler();
    printf("============================================================\n");
    printf("Sotlas Native Test Suite\n");
    printf("Executando %d arquivo(s) de teste com backend %s\n", g_test_file_count, cc);
    printf("============================================================\n");

    clock_t start_time = clock();
    int pass_count = 0;
    int fail_count = 0;

    uint8_t *source = (uint8_t *)malloc(MAX_SOURCE_SIZE);
    uint8_t *output = (uint8_t *)malloc(MAX_OUTPUT_SIZE);
    if (!source || !output) {
        fprintf(stderr, "sotlas-test: erro de alocacao de memoria para os testes\n");
        if (source) free(source);
        if (output) free(output);
        return 1;
    }

    for (int i = 0; i < g_test_file_count; i++) {
        const char *tpath = g_test_files[i];
        g_num_loaded_files = 0;
        source[0] = 0;
        size_t source_len = 0;

        if (!load_source_file(tpath, source, &source_len, MAX_SOURCE_SIZE)) {
            printf("  \033[31m[FAIL]\033[0m %-45s (nao foi possivel ler arquivo)\n", tpath);
            fail_count++;
            continue;
        }

        memset(output, 0, MAX_OUTPUT_SIZE);
        size_t out_len = sotlas_compile(source, output, MAX_OUTPUT_SIZE);
        if (out_len == 0) {
            printf("  \033[31m[FAIL]\033[0m %-45s (falha na compilacao Sotlas)\n", tpath);
            fail_count++;
            continue;
        }

        char temp_c[512];
        char temp_exe[512];
#if defined(_WIN32)
        snprintf(temp_c, sizeof(temp_c), "%s.test_tmp.c", tpath);
        snprintf(temp_exe, sizeof(temp_exe), "%s.test_tmp.exe", tpath);
#else
        snprintf(temp_c, sizeof(temp_c), "%s.test_tmp.c", tpath);
        snprintf(temp_exe, sizeof(temp_exe), "%s.test_tmp.bin", tpath);
#endif

        FILE *tf = fopen(temp_c, "wb");
        if (!tf) {
            printf("  \033[31m[FAIL]\033[0m %-45s (erro ao criar temp C)\n", tpath);
            fail_count++;
            continue;
        }
        fwrite(output, 1, out_len, tf);
        fclose(tf);

        char build_cmd[1024];
#if defined(_WIN32)
        for (char *c = temp_c; *c; c++) { if (*c == '/') *c = '\\'; }
        for (char *c = temp_exe; *c; c++) { if (*c == '/') *c = '\\'; }
        if (verbose) {
            snprintf(build_cmd, sizeof(build_cmd), "\"\"%s\" -O2 \"%s\" -o \"%s\"\"", cc, temp_c, temp_exe);
        } else {
            snprintf(build_cmd, sizeof(build_cmd), "\"\"%s\" -O2 \"%s\" -o \"%s\" >nul 2>&1\"", cc, temp_c, temp_exe);
        }
#else
        if (verbose) {
            snprintf(build_cmd, sizeof(build_cmd), "\"%s\" -O2 \"%s\" -o \"%s\"", cc, temp_c, temp_exe);
        } else {
            snprintf(build_cmd, sizeof(build_cmd), "\"%s\" -O2 \"%s\" -o \"%s\" >/dev/null 2>&1", cc, temp_c, temp_exe);
        }
#endif
        int b_ret = system(build_cmd);
        remove(temp_c);

        if (b_ret != 0) {
            printf("  \033[31m[FAIL]\033[0m %-45s (erro de compilacao/link C)\n", tpath);
            fail_count++;
            continue;
        }

        char run_cmd[1024];
#if defined(_WIN32)
        if (verbose) {
            snprintf(run_cmd, sizeof(run_cmd), "\"\"%s\"\"", temp_exe);
        } else {
            snprintf(run_cmd, sizeof(run_cmd), "\"\"%s\" >nul 2>&1\"", temp_exe);
        }
#else
        if (verbose) {
            snprintf(run_cmd, sizeof(run_cmd), "\"%s\"", temp_exe);
        } else {
            snprintf(run_cmd, sizeof(run_cmd), "\"%s\" >/dev/null 2>&1", temp_exe);
        }
#endif
        int run_ret = system(run_cmd);
        remove(temp_exe);

        if (run_ret == 0) {
            printf("  \033[32m[PASS]\033[0m %s\n", tpath);
            pass_count++;
        } else {
            printf("  \033[31m[FAIL]\033[0m %-45s (saida: %d / falha no probe)\n", tpath, run_ret);
            fail_count++;
        }
    }

    free(source);
    free(output);

    double elapsed = (double)(clock() - start_time) / CLOCKS_PER_SEC;
    printf("============================================================\n");
    printf("Resultado: %d aprovados, %d falhas (Total: %d) em %.2fs\n", pass_count, fail_count, g_test_file_count, elapsed);
    if (fail_count == 0) {
        printf("\033[32mTodos os testes nativos passaram com sucesso!\033[0m\n");
    } else {
        printf("\033[31mAlguns testes falharam!\033[0m\n");
    }
    printf("============================================================\n");

    return (fail_count == 0) ? 0 : 1;
}

// ============================================================================
// Gerenciador de Pacotes e Manifesto Nativo (Sotlas.toml)
// ============================================================================

typedef struct {
    char name[128];
    char version[32];
    char edition[16];
    char license[64];
    char target_type[16]; // "bin" ou "lib"
    char dependencies[32][128];
    char dep_versions[32][64];
    int dep_count;
} NativePackageManifest;

static void init_default_manifest(NativePackageManifest *m, const char *name, bool is_lib) {
    memset(m, 0, sizeof(*m));
    strncpy(m->name, name ? name : "unnamed", sizeof(m->name) - 1);
    strcpy(m->version, "0.1.0");
    strcpy(m->edition, "2026");
    strcpy(m->license, "Apache-2.0");
    strcpy(m->target_type, is_lib ? "lib" : "bin");
    m->dep_count = 0;
}

static bool parse_manifest_file(const char *toml_path, NativePackageManifest *m) {
    FILE *f = fopen(toml_path, "rb");
    if (!f) return false;

    fseek(f, 0, SEEK_END);
    long fsize = ftell(f);
    fseek(f, 0, SEEK_SET);
    if (fsize <= 0) {
        fclose(f);
        return false;
    }

    char *buf = (char *)malloc(fsize + 1);
    if (!buf) { fclose(f); return false; }
    size_t rd = fread(buf, 1, fsize, f);
    buf[rd] = 0;
    fclose(f);

    init_default_manifest(m, "unnamed", false);

    char current_section[64] = "package";
    char *line = strtok(buf, "\r\n");
    while (line) {
        while (*line == ' ' || *line == '\t') line++;
        if (*line == 0 || *line == '#') {
            line = strtok(NULL, "\r\n");
            continue;
        }

        if (line[0] == '[') {
            char *end_b = strchr(line, ']');
            if (end_b) {
                *end_b = 0;
                strncpy(current_section, line + 1, sizeof(current_section) - 1);
                for (char *c = current_section; *c; c++) {
                    if (*c >= 'A' && *c <= 'Z') *c = *c + 32;
                }
            }
            line = strtok(NULL, "\r\n");
            continue;
        }

        char *eq = strchr(line, '=');
        if (eq) {
            *eq = 0;
            char *key = line;
            char *val = eq + 1;
            while (*key == ' ' || *key == '\t') key++;
            char *k_end = key + strlen(key) - 1;
            while (k_end >= key && (*k_end == ' ' || *k_end == '\t')) *k_end-- = 0;

            while (*val == ' ' || *val == '\t') val++;
            char *v_end = val + strlen(val) - 1;
            while (v_end >= val && (*v_end == ' ' || *v_end == '\t' || *v_end == '\r' || *v_end == '\n')) *v_end-- = 0;

            if (*val == '"' || *val == '\'') {
                val++;
                if (v_end >= val && (*v_end == '"' || *v_end == '\'')) *v_end = 0;
            }

            if (strcmp(current_section, "package") == 0) {
                if (strcmp(key, "name") == 0) {
                    strncpy(m->name, val, sizeof(m->name) - 1);
                } else if (strcmp(key, "version") == 0) {
                    strncpy(m->version, val, sizeof(m->version) - 1);
                } else if (strcmp(key, "edition") == 0) {
                    strncpy(m->edition, val, sizeof(m->edition) - 1);
                } else if (strcmp(key, "license") == 0) {
                    strncpy(m->license, val, sizeof(m->license) - 1);
                } else if (strcmp(key, "target_type") == 0) {
                    strncpy(m->target_type, val, sizeof(m->target_type) - 1);
                }
            } else if (strcmp(current_section, "dependencies") == 0) {
                if (m->dep_count < 32 && key[0] != 0) {
                    strncpy(m->dependencies[m->dep_count], key, sizeof(m->dependencies[0]) - 1);
                    strncpy(m->dep_versions[m->dep_count], val, sizeof(m->dep_versions[0]) - 1);
                    m->dep_count++;
                }
            }
        }
        line = strtok(NULL, "\r\n");
    }

    free(buf);
    return true;
}

static bool write_manifest_file(const char *toml_path, const NativePackageManifest *m) {
    FILE *f = fopen(toml_path, "wb");
    if (!f) return false;

    fprintf(f, "[package]\n");
    fprintf(f, "name = \"%s\"\n", m->name);
    fprintf(f, "version = \"%s\"\n", m->version);
    fprintf(f, "edition = \"%s\"\n", m->edition);
    fprintf(f, "license = \"%s\"\n", m->license);
    fprintf(f, "target_type = \"%s\"\n", m->target_type);
    fprintf(f, "authors = [\"Sotlas Developer\"]\n\n");

    fprintf(f, "[dependencies]\n");
    for (int i = 0; i < m->dep_count; i++) {
        fprintf(f, "%s = \"%s\"\n", m->dependencies[i], m->dep_versions[i]);
    }
    fprintf(f, "\n");
    fclose(f);
    return true;
}

static int run_init_internal(const char *dir_path, const char *pkg_name, bool is_lib) {
    char toml_path[512];
    snprintf(toml_path, sizeof(toml_path), "%s/Sotlas.toml", dir_path);

    NativePackageManifest manifest;
    init_default_manifest(&manifest, pkg_name, is_lib);
    if (!write_manifest_file(toml_path, &manifest)) {
        fprintf(stderr, "sotlas: erro ao criar %s\n", toml_path);
        return 1;
    }

    char src_dir[512];
    snprintf(src_dir, sizeof(src_dir), "%s/src", dir_path);
    make_dir(src_dir);

    char entry_file[512];
    snprintf(entry_file, sizeof(entry_file), "%s/src/%s", dir_path, is_lib ? "lib.sotlas" : "main.sotlas");

    FILE *ef = fopen(entry_file, "wb");
    if (ef) {
        if (is_lib) {
            fprintf(ef, "module %s;\n\n", pkg_name);
            fprintf(ef, "pub fn calculate(a: u32, b: u32) -> u32 {\n");
            fprintf(ef, "    return a + b;\n");
            fprintf(ef, "}\n");
        } else {
            fprintf(ef, "module %s;\n\n", pkg_name);
            fprintf(ef, "pub fn main() -> i32 {\n");
            fprintf(ef, "    return 0;\n");
            fprintf(ef, "}\n");
        }
        fclose(ef);
    }

    char gitignore[512];
    snprintf(gitignore, sizeof(gitignore), "%s/.gitignore", dir_path);
    if (!file_exists(gitignore)) {
        FILE *gf = fopen(gitignore, "wb");
        if (gf) {
            fprintf(gf, "build/\ntarget/\n*.bin\n*.tmp.c\n");
            fclose(gf);
        }
    }

    printf("sotlas: pacote '%s' inicializado com sucesso em %s\n", pkg_name, dir_path);
    return 0;
}

static int run_new_command(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "sotlas: erro: esperado nome do projeto apos 'new'\n");
        return 1;
    }
    const char *dir_path = argv[2];
    bool is_lib = false;
    for (int i = 3; i < argc; i++) {
        if (strcmp(argv[i], "--lib") == 0) is_lib = true;
    }

    const char *pkg_name = dir_path;
    const char *s1 = strrchr(dir_path, '/');
    const char *s2 = strrchr(dir_path, '\\');
    const char *last_s = (s1 > s2) ? s1 : s2;
    if (last_s && *(last_s + 1)) {
        pkg_name = last_s + 1;
    }

    make_dir_recursive(dir_path);
    return run_init_internal(dir_path, pkg_name, is_lib);
}

static int run_init_command(int argc, char **argv) {
    bool is_lib = false;
    for (int i = 2; i < argc; i++) {
        if (strcmp(argv[i], "--lib") == 0) is_lib = true;
    }
    char cwd_buf[256];
    const char *name = "sotlas_app";
#if defined(_WIN32)
    GetCurrentDirectoryA(sizeof(cwd_buf), cwd_buf);
    char *last_slash = strrchr(cwd_buf, '\\');
    if (last_slash && *(last_slash + 1)) name = last_slash + 1;
#endif
    return run_init_internal(".", name, is_lib);
}

static int run_add_command(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "sotlas: erro: esperado nome da dependencia apos 'add'\n");
        return 1;
    }
    const char *dep_name = argv[2];
    const char *version = "^0.1.0";
    const char *proj_dir = ".";

    for (int i = 3; i < argc; i++) {
        if ((strcmp(argv[i], "--version") == 0 || strcmp(argv[i], "-v") == 0) && (i + 1 < argc)) {
            version = argv[++i];
        } else if ((strcmp(argv[i], "--path") == 0 || strcmp(argv[i], "-p") == 0) && (i + 1 < argc)) {
            proj_dir = argv[++i];
        }
    }

    char toml_path[512];
    snprintf(toml_path, sizeof(toml_path), "%s/Sotlas.toml", proj_dir);
    if (!file_exists(toml_path)) {
        fprintf(stderr, "sotlas: erro: Sotlas.toml nao encontrado em %s\n", proj_dir);
        return 1;
    }

    NativePackageManifest manifest;
    if (!parse_manifest_file(toml_path, &manifest)) {
        fprintf(stderr, "sotlas: erro ao processar Sotlas.toml em %s\n", proj_dir);
        return 1;
    }

    bool found = false;
    for (int i = 0; i < manifest.dep_count; i++) {
        if (strcmp(manifest.dependencies[i], dep_name) == 0) {
            strncpy(manifest.dep_versions[i], version, sizeof(manifest.dep_versions[0]) - 1);
            found = true;
            break;
        }
    }
    if (!found && manifest.dep_count < 32) {
        strncpy(manifest.dependencies[manifest.dep_count], dep_name, sizeof(manifest.dependencies[0]) - 1);
        strncpy(manifest.dep_versions[manifest.dep_count], version, sizeof(manifest.dep_versions[0]) - 1);
        manifest.dep_count++;
    }

    write_manifest_file(toml_path, &manifest);
    printf("sotlas: adicionada dependência '%s = \"%s\"' ao Sotlas.toml\n", dep_name, version);
    return 0;
}

static int run_build_command(int argc, char **argv) {
    const char *proj_dir = ".";
    const char *output_file = NULL;

    for (int i = 2; i < argc; i++) {
        if ((strcmp(argv[i], "--path") == 0 || strcmp(argv[i], "-p") == 0) && (i + 1 < argc)) {
            proj_dir = argv[++i];
        } else if (strcmp(argv[i], "-o") == 0 && (i + 1 < argc)) {
            output_file = argv[++i];
        }
    }

    char toml_path[512];
    snprintf(toml_path, sizeof(toml_path), "%s/Sotlas.toml", proj_dir);
    if (!file_exists(toml_path)) {
        fprintf(stderr, "sotlas: erro: Sotlas.toml nao encontrado em %s\n", proj_dir);
        return 1;
    }

    NativePackageManifest manifest;
    if (!parse_manifest_file(toml_path, &manifest)) {
        fprintf(stderr, "sotlas: erro ao ler Sotlas.toml em %s\n", proj_dir);
        return 1;
    }

    bool is_lib = (strcmp(manifest.target_type, "lib") == 0);
    char entry_file[512];
    snprintf(entry_file, sizeof(entry_file), "%s/src/%s", proj_dir, is_lib ? "lib.sotlas" : "main.sotlas");

    if (!file_exists(entry_file)) {
        snprintf(entry_file, sizeof(entry_file), "%s/src/main.sotlas", proj_dir);
        if (!file_exists(entry_file)) {
            snprintf(entry_file, sizeof(entry_file), "%s/src/lib.sotlas", proj_dir);
            if (!file_exists(entry_file)) {
                fprintf(stderr, "sotlas: erro: arquivo de entrada principal nao encontrado em %s/src/\n", proj_dir);
                return 1;
            }
        }
    }

    char build_dir[512];
    snprintf(build_dir, sizeof(build_dir), "%s/build", proj_dir);
    make_dir_recursive(build_dir);

    const char *clean_name = manifest.name;
    const char *s1 = strrchr(manifest.name, '/');
    const char *s2 = strrchr(manifest.name, '\\');
    const char *last_s = (s1 > s2) ? s1 : s2;
    if (last_s && *(last_s + 1)) {
        clean_name = last_s + 1;
    }

    char out_c[512];
    snprintf(out_c, sizeof(out_c), "%s/%s.c", build_dir, clean_name);

    uint8_t *source = (uint8_t *)malloc(MAX_SOURCE_SIZE);
    uint8_t *output = (uint8_t *)malloc(MAX_OUTPUT_SIZE);
    if (!source || !output) {
        fprintf(stderr, "sotlas: erro de memoria durante build\n");
        if (source) free(source);
        if (output) free(output);
        return 1;
    }

    g_num_loaded_files = 0;
    source[0] = 0;
    size_t source_len = 0;
    if (!load_source_file(entry_file, source, &source_len, MAX_SOURCE_SIZE)) {
        fprintf(stderr, "sotlas: erro ao carregar arquivo %s\n", entry_file);
        free(source);
        free(output);
        return 1;
    }

    memset(output, 0, MAX_OUTPUT_SIZE);
    size_t out_len = sotlas_compile(source, output, MAX_OUTPUT_SIZE);
    free(source);

    if (out_len == 0) {
        fprintf(stderr, "sotlas: erro de compilacao no projeto '%s'\n", manifest.name);
        free(output);
        return 1;
    }

    FILE *cf = fopen(out_c, "wb");
    if (!cf) {
        fprintf(stderr, "sotlas: erro ao escrever em %s\n", out_c);
        free(output);
        return 1;
    }
    fwrite(output, 1, out_len, cf);
    fclose(cf);
    free(output);

    printf("sotlas: pacote '%s' v%s compilado -> %s\n", manifest.name, manifest.version, out_c);

    if (!is_lib) {
        char out_bin[512];
        if (output_file) {
            strncpy(out_bin, output_file, sizeof(out_bin) - 1);
        } else {
#if defined(_WIN32)
            snprintf(out_bin, sizeof(out_bin), "%s/%s.exe", build_dir, clean_name);
#else
            snprintf(out_bin, sizeof(out_bin), "%s/%s.bin", build_dir, clean_name);
#endif
        }

        const char *cc = find_c_compiler();
        char build_cmd[1024];
#if defined(_WIN32)
        for (char *c = out_c; *c; c++) { if (*c == '/') *c = '\\'; }
        for (char *c = out_bin; *c; c++) { if (*c == '/') *c = '\\'; }
        snprintf(build_cmd, sizeof(build_cmd), "\"\"%s\" -O2 \"%s\" -o \"%s\"\"", cc, out_c, out_bin);
#else
        snprintf(build_cmd, sizeof(build_cmd), "\"%s\" -O2 \"%s\" -o \"%s\"", cc, out_c, out_bin);
#endif
        int b_ret = system(build_cmd);
        if (b_ret == 0) {
            printf("sotlas: executavel binario gerado com sucesso -> %s\n", out_bin);
        } else {
            fprintf(stderr, "sotlas: aviso: falha ao linkar binario nativo com %s\n", cc);
        }
    }

    return 0;
}

static bool is_ident_char(char c) {
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '_';
}

static size_t format_sotlas_code(const char *src, char *out, size_t max_out) {
    if (!src || !out || max_out == 0) return 0;

    out[0] = 0;
    size_t out_pos = 0;
    int indent_level = 0;
    bool in_block_comment = false;

    const char *p = src;
    while (*p) {
        const char *line_start = p;
        while (*p && *p != '\n' && *p != '\r') p++;
        size_t raw_len = p - line_start;
        if (*p == '\r' && *(p + 1) == '\n') p += 2;
        else if (*p == '\n' || *p == '\r') p++;

        const char *s = line_start;
        const char *e = line_start + raw_len;
        while (s < e && (*s == ' ' || *s == '\t')) s++;
        while (e > s && (*(e - 1) == ' ' || *(e - 1) == '\t')) e--;
        size_t len = e - s;

        if (len == 0) {
            if (out_pos + 1 < max_out) {
                out[out_pos++] = '\n';
                out[out_pos] = 0;
            }
            continue;
        }

        char stripped[1024];
        if (len >= sizeof(stripped)) len = sizeof(stripped) - 1;
        memcpy(stripped, s, len);
        stripped[len] = 0;

        if (strncmp(stripped, "/*", 2) == 0 && strstr(stripped, "*/") == NULL) {
            in_block_comment = true;
        }

        if (!in_block_comment && (stripped[0] == '}' || (stripped[0] == '}' && stripped[1] == ';'))) {
            if (indent_level > 0) indent_level--;
        }

        for (int ind = 0; ind < indent_level * 4; ind++) {
            if (out_pos + 1 < max_out) out[out_pos++] = ' ';
        }

        if (in_block_comment || strncmp(stripped, "//", 2) == 0 || strncmp(stripped, "/*", 2) == 0) {
            for (size_t k = 0; k < len; k++) {
                if (out_pos + 1 < max_out) out[out_pos++] = stripped[k];
            }
            if (in_block_comment && strstr(stripped, "*/") != NULL) {
                in_block_comment = false;
            }
        } else {
            for (size_t k = 0; k < len; k++) {
                char ch = stripped[k];

                if (ch == '-' && k + 1 < len && stripped[k + 1] == '>') {
                    if (out_pos > 0 && out[out_pos - 1] != ' ') {
                        if (out_pos + 1 < max_out) out[out_pos++] = ' ';
                    }
                    if (out_pos + 2 < max_out) {
                        out[out_pos++] = '-';
                        out[out_pos++] = '>';
                    }
                    if (k + 2 < len && stripped[k + 2] != ' ') {
                        if (out_pos + 1 < max_out) out[out_pos++] = ' ';
                    }
                    k++;
                    continue;
                }

                if (ch == '{') {
                    if (out_pos > 0 && out[out_pos - 1] != ' ') {
                        if (out_pos + 1 < max_out) out[out_pos++] = ' ';
                    }
                    if (out_pos + 1 < max_out) out[out_pos++] = '{';
                    continue;
                }

                if (ch == ',') {
                    if (out_pos + 1 < max_out) out[out_pos++] = ',';
                    if (k + 1 < len && stripped[k + 1] != ' ') {
                        if (out_pos + 1 < max_out) out[out_pos++] = ' ';
                    }
                    continue;
                }

                if (ch == ':' && (k + 1 < len && stripped[k + 1] != ':') && (k == 0 || stripped[k - 1] != ':')) {
                    if (out_pos > 0 && out[out_pos - 1] == ' ') {
                        out_pos--;
                    }
                    if (out_pos + 1 < max_out) out[out_pos++] = ':';
                    if (k + 1 < len && stripped[k + 1] != ' ') {
                        if (out_pos + 1 < max_out) out[out_pos++] = ' ';
                    }
                    continue;
                }

                if (out_pos + 1 < max_out) out[out_pos++] = ch;
            }
        }

        if (out_pos + 1 < max_out) {
            out[out_pos++] = '\n';
            out[out_pos] = 0;
        }

        if (!in_block_comment) {
            int opens = 0;
            int closes = 0;
            for (size_t k = 0; k < len; k++) {
                if (stripped[k] == '{') opens++;
                else if (stripped[k] == '}') closes++;
            }
            if (stripped[0] == '}' || (stripped[0] == '}' && stripped[1] == ';')) {
                indent_level += opens;
            } else {
                indent_level += (opens - closes);
            }
            if (indent_level < 0) indent_level = 0;
        }
    }

    out[out_pos] = 0;
    return out_pos;
}

static int run_fmt_command(int argc, char **argv) {
    bool check_only = false;
    const char *target = ".";

    for (int i = 2; i < argc; i++) {
        if (strcmp(argv[i], "--check") == 0) {
            check_only = true;
        } else if (argv[i][0] != '-') {
            target = argv[i];
        }
    }

    char fmt_files[MAX_TEST_FILES][512];
    int fmt_file_count = 0;

    if (is_directory(target)) {
        g_test_file_count = 0;
        scan_test_dir(target);
        for (int i = 0; i < g_test_file_count; i++) {
            strncpy(fmt_files[fmt_file_count++], g_test_files[i], 511);
        }
    } else if (file_exists(target)) {
        strncpy(fmt_files[fmt_file_count++], target, 511);
    } else {
        char with_ext[512];
        snprintf(with_ext, sizeof(with_ext), "%s.sotlas", target);
        if (file_exists(with_ext)) {
            strncpy(fmt_files[fmt_file_count++], with_ext, 511);
        } else {
            fprintf(stderr, "sotlas fmt: arquivo ou diretorio nao encontrado: %s\n", target);
            return 1;
        }
    }

    if (fmt_file_count == 0) {
        printf("sotlas fmt: nenhum arquivo .sotlas encontrado em %s\n", target);
        return 0;
    }

    int files_needing_fmt = 0;
    int files_formatted = 0;

    for (int i = 0; i < fmt_file_count; i++) {
        const char *fpath = fmt_files[i];
        FILE *f = fopen(fpath, "rb");
        if (!f) continue;
        fseek(f, 0, SEEK_END);
        long fsize = ftell(f);
        fseek(f, 0, SEEK_SET);
        if (fsize <= 0) { fclose(f); continue; }

        char *buf = (char *)malloc(fsize + 1);
        char *out = (char *)malloc(fsize * 2 + 1024);
        if (!buf || !out) {
            if (buf) free(buf);
            if (out) free(out);
            fclose(f);
            continue;
        }
        size_t rd = fread(buf, 1, fsize, f);
        buf[rd] = 0;
        fclose(f);

        size_t out_len = format_sotlas_code(buf, out, fsize * 2 + 1024);
        if (strcmp(buf, out) != 0) {
            files_needing_fmt++;
            if (check_only) {
                printf("sotlas fmt: formatacao necessaria em %s\n", fpath);
            } else {
                FILE *wf = fopen(fpath, "wb");
                if (wf) {
                    fwrite(out, 1, out_len, wf);
                    fclose(wf);
                    files_formatted++;
                    printf("sotlas fmt: formatado %s\n", fpath);
                }
            }
        }
        free(buf);
        free(out);
    }

    if (check_only) {
        if (files_needing_fmt > 0) {
            printf("sotlas fmt: %d arquivo(s) precisam de formatacao.\n", files_needing_fmt);
            return 1;
        } else {
            printf("sotlas fmt: todos os arquivos estao corretamente formatados.\n");
            return 0;
        }
    } else {
        printf("sotlas fmt: %d arquivo(s) formatados com sucesso.\n", files_formatted);
        return 0;
    }
}

static int run_lint_command(int argc, char **argv) {
    const char *target = ".";
    for (int i = 2; i < argc; i++) {
        if (argv[i][0] != '-') {
            target = argv[i];
        }
    }

    char lint_files[MAX_TEST_FILES][512];
    int lint_file_count = 0;

    if (is_directory(target)) {
        g_test_file_count = 0;
        scan_test_dir(target);
        for (int i = 0; i < g_test_file_count; i++) {
            strncpy(lint_files[lint_file_count++], g_test_files[i], 511);
        }
    } else if (file_exists(target)) {
        strncpy(lint_files[lint_file_count++], target, 511);
    } else {
        char with_ext[512];
        snprintf(with_ext, sizeof(with_ext), "%s.sotlas", target);
        if (file_exists(with_ext)) {
            strncpy(lint_files[lint_file_count++], with_ext, 511);
        } else {
            fprintf(stderr, "sotlas lint: arquivo ou diretorio nao encontrado: %s\n", target);
            return 1;
        }
    }

    if (lint_file_count == 0) {
        printf("sotlas lint: nenhum arquivo .sotlas encontrado em %s\n", target);
        return 0;
    }

    int total_warnings = 0;

    for (int i = 0; i < lint_file_count; i++) {
        const char *fpath = lint_files[i];
        FILE *f = fopen(fpath, "rb");
        if (!f) continue;
        fseek(f, 0, SEEK_END);
        long fsize = ftell(f);
        fseek(f, 0, SEEK_SET);
        if (fsize <= 0) { fclose(f); continue; }

        char *buf = (char *)malloc(fsize + 1);
        if (!buf) { fclose(f); continue; }
        size_t rd = fread(buf, 1, fsize, f);
        buf[rd] = 0;
        fclose(f);

        int line_num = 1;
        char *p = buf;
        while (*p) {
            char *line_start = p;
            while (*p && *p != '\n' && *p != '\r') p++;
            size_t line_len = p - line_start;
            if (*p == '\r' && *(p + 1) == '\n') p += 2;
            else if (*p == '\n' || *p == '\r') p++;

            char line[1024];
            if (line_len >= sizeof(line)) line_len = sizeof(line) - 1;
            memcpy(line, line_start, line_len);
            line[line_len] = 0;

            char *s = line;
            while (*s == ' ' || *s == '\t') s++;

            if (line_len > 120 && strncmp(s, "//", 2) != 0) {
                printf("%s:%d:121: warning: [line-length] Linha com %zu caracteres excede o limite de 120\n", fpath, line_num, line_len);
                total_warnings++;
            }

            for (size_t col = 0; col < line_len; col++) {
                if (line[col] == '\t' && strncmp(s, "//", 2) != 0) {
                    printf("%s:%d:%zu: warning: [no-tabs] Uso de caractere de tabulacao (esperado 4 espacos)\n", fpath, line_num, col + 1);
                    total_warnings++;
                    break;
                }
            }

            char *fn_pos = strstr(line, "fn ");
            if (fn_pos && (fn_pos == line || *(fn_pos - 1) == ' ' || *(fn_pos - 1) == '\t')) {
                char *fn_name = fn_pos + 3;
                while (*fn_name == ' ') fn_name++;
                if (*fn_name >= 'A' && *fn_name <= 'Z') {
                    char name_buf[64];
                    size_t nk = 0;
                    while (is_ident_char(fn_name[nk]) && nk < 63) {
                        name_buf[nk] = fn_name[nk];
                        nk++;
                    }
                    name_buf[nk] = 0;
                    size_t col = (fn_name - line) + 1;
                    printf("%s:%d:%zu: warning: [naming-fn-snake-case] Funcao '%s' deve iniciar com letra minuscula (snake_case)\n", fpath, line_num, col, name_buf);
                    total_warnings++;
                }
            }

            char *st_pos = strstr(line, "struct ");
            if (st_pos && (st_pos == line || *(st_pos - 1) == ' ' || *(st_pos - 1) == '\t')) {
                char *st_name = st_pos + 7;
                while (*st_name == ' ') st_name++;
                if (*st_name >= 'a' && *st_name <= 'z') {
                    char name_buf[64];
                    size_t nk = 0;
                    while (is_ident_char(st_name[nk]) && nk < 63) {
                        name_buf[nk] = st_name[nk];
                        nk++;
                    }
                    name_buf[nk] = 0;
                    size_t col = (st_name - line) + 1;
                    printf("%s:%d:%zu: warning: [naming-type-pascal-case] Struct '%s' deve iniciar com letra maiuscula (PascalCase)\n", fpath, line_num, col, name_buf);
                    total_warnings++;
                }
            }

            line_num++;
        }
        free(buf);
    }

    if (total_warnings == 0) {
        printf("sotlas lint: 0 avisos encontrados em %d arquivo(s).\n", lint_file_count);
        return 0;
    } else {
        printf("sotlas lint: %d aviso(s) encontrado(s).\n", total_warnings);
        return 1;
    }
}

int main(int argc, char **argv) {
#if defined(_WIN32)
    HANDLE hOut = GetStdHandle(STD_OUTPUT_HANDLE);
    if (hOut != INVALID_HANDLE_VALUE) {
        DWORD dwMode = 0;
        if (GetConsoleMode(hOut, &dwMode)) {
            SetConsoleMode(hOut, dwMode | ENABLE_VIRTUAL_TERMINAL_PROCESSING);
        }
    }
#endif

    if (argc < 2) {
        print_usage(argv[0]);
        return 1;
    }

    if (strcmp(argv[1], "--version") == 0 || strcmp(argv[1], "-v") == 0) {
        printf("sotlas 1.0.0-dev (x86_64-pc-windows-msvc)\n");
        return 0;
    }

    if (strcmp(argv[1], "test") == 0) {
        return run_test_command(argc, argv);
    }
    if (strcmp(argv[1], "fmt") == 0) {
        return run_fmt_command(argc, argv);
    }
    if (strcmp(argv[1], "lint") == 0) {
        return run_lint_command(argc, argv);
    }
    if (strcmp(argv[1], "init") == 0) {
        return run_init_command(argc, argv);
    }
    if (strcmp(argv[1], "new") == 0) {
        return run_new_command(argc, argv);
    }
    if (strcmp(argv[1], "build") == 0) {
        return run_build_command(argc, argv);
    }
    if (strcmp(argv[1], "add") == 0) {
        return run_add_command(argc, argv);
    }

    bool is_run = false;
    const char *output_file = NULL;
    bool emit_c_only = false;

    #define MAX_INPUT_FILES 64
    const char *input_files[MAX_INPUT_FILES];
    int input_file_count = 0;

    int arg_idx = 1;
    if (strcmp(argv[1], "run") == 0) {
        is_run = true;
        arg_idx = 2;
        if (argc < 3) {
            fprintf(stderr, "sotlas: error: expected .sotlas file after 'run'\n");
            return 1;
        }
    } else if (strcmp(argv[1], "compile") == 0) {
        arg_idx = 2;
        if (argc < 3) {
            fprintf(stderr, "sotlas: error: expected .sotlas file after 'compile'\n");
            return 1;
        }
    }

    for (int i = arg_idx; i < argc; i++) {
        if (strcmp(argv[i], "-o") == 0 && (i + 1 < argc)) {
            output_file = argv[i + 1];
            i++;
        } else if (strcmp(argv[i], "--emit-c") == 0) {
            emit_c_only = true;
        } else if (argv[i][0] != '-') {
            if (input_file_count < MAX_INPUT_FILES) {
                input_files[input_file_count++] = argv[i];
            }
        }
    }

    if (input_file_count == 0) {
        fprintf(stderr, "sotlas: error: no input files specified\n");
        return 1;
    }

    uint8_t *source = (uint8_t *)malloc(MAX_SOURCE_SIZE);
    if (!source) {
        fprintf(stderr, "sotlas: error: memory allocation failed\n");
        return 1;
    }
    source[0] = 0;
    size_t source_len = 0;

    for (int i = 0; i < input_file_count; i++) {
        if (!load_source_file(input_files[i], source, &source_len, MAX_SOURCE_SIZE)) {
            fprintf(stderr, "sotlas: error: could not open file '%s'\n", input_files[i]);
            free(source);
            return 1;
        }
    }

    uint8_t *output = (uint8_t *)malloc(MAX_OUTPUT_SIZE);
    if (!output) {
        fprintf(stderr, "sotlas: error: memory allocation failed for output buffer\n");
        free(source);
        return 1;
    }
    memset(output, 0, MAX_OUTPUT_SIZE);

    size_t out_len = sotlas_compile(source, output, MAX_OUTPUT_SIZE);
    free(source);

    if (out_len == 0) {
        fprintf(stderr, "sotlas: error: project compilation failed\n");
        free(output);
        return 1;
    }

    if (is_run) {
        char temp_c[512];
        char temp_exe[512];
#if defined(_WIN32)
        snprintf(temp_c, sizeof(temp_c), "%s.run_tmp.c", input_files[0]);
        snprintf(temp_exe, sizeof(temp_exe), "%s.run_tmp.exe", input_files[0]);
#else
        snprintf(temp_c, sizeof(temp_c), "%s.run_tmp.c", input_files[0]);
        snprintf(temp_exe, sizeof(temp_exe), "%s.run_tmp.bin", input_files[0]);
#endif
        FILE *tf = fopen(temp_c, "wb");
        if (!tf) {
            fprintf(stderr, "sotlas: error: could not create temporary file '%s'\n", temp_c);
            free(output);
            return 1;
        }
        fwrite(output, 1, out_len, tf);
        fclose(tf);

        const char *cc = find_c_compiler();
        char build_cmd[1024];
#if defined(_WIN32)
        for (char *c = temp_c; *c; c++) { if (*c == '/') *c = '\\'; }
        for (char *c = temp_exe; *c; c++) { if (*c == '/') *c = '\\'; }
        snprintf(build_cmd, sizeof(build_cmd), "\"\"%s\" -O2 \"%s\" -o \"%s\"\"", cc, temp_c, temp_exe);
#else
        snprintf(build_cmd, sizeof(build_cmd), "\"%s\" -O2 \"%s\" -o \"%s\"", cc, temp_c, temp_exe);
#endif
        int b_ret = system(build_cmd);
        remove(temp_c);

        if (b_ret != 0) {
            fprintf(stderr, "sotlas: error: failed to link executable with '%s'\n", cc);
            free(output);
            return b_ret;
        }

        char run_cmd[1024];
#if defined(_WIN32)
        snprintf(run_cmd, sizeof(run_cmd), "\"\"%s\"\"", temp_exe);
#else
        snprintf(run_cmd, sizeof(run_cmd), "\"%s\"", temp_exe);
#endif
        int run_ret = system(run_cmd);
        remove(temp_exe);
        free(output);
        return run_ret;
    }

    if (output_file) {
        bool is_binary_target = ends_with(output_file, ".exe") || ends_with(output_file, ".obj") ||
                                 ends_with(output_file, ".o") || ends_with(output_file, ".bin");

        if (is_binary_target && !emit_c_only) {
            char temp_c[512];
            snprintf(temp_c, sizeof(temp_c), "%s.tmp.c", output_file);
            FILE *out_f = fopen(temp_c, "wb");
            if (!out_f) {
                fprintf(stderr, "sotlas: error: could not write to '%s'\n", temp_c);
                free(output);
                return 1;
            }
            fwrite(output, 1, out_len, out_f);
            fclose(out_f);

            const char *cc = find_c_compiler();
            char build_cmd[1024];
#if defined(_WIN32)
            snprintf(build_cmd, sizeof(build_cmd), "\"\"%s\" -O2 \"%s\" -o \"%s\"\"", cc, temp_c, output_file);
#else
            snprintf(build_cmd, sizeof(build_cmd), "\"%s\" -O2 \"%s\" -o \"%s\"", cc, temp_c, output_file);
#endif
            int b_ret = system(build_cmd);
            remove(temp_c);

            if (b_ret != 0) {
                fprintf(stderr, "sotlas: error compiling native binary with '%s'\n", cc);
                free(output);
                return b_ret;
            }
            printf("sotlas: compiled and linked -> '%s'\n", output_file);
        } else {
            FILE *out_f = fopen(output_file, "wb");
            if (!out_f) {
                fprintf(stderr, "sotlas: error writing to '%s'\n", output_file);
                free(output);
                return 1;
            }
            fwrite(output, 1, out_len, out_f);
            fclose(out_f);
            printf("sotlas: compiled -> '%s' (%zu bytes)\n", output_file, out_len);
        }
    } else {
        printf("%s\n", (char *)output);
    }

    free(output);
    return 0;
}
