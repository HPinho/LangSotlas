#include "runtime.h"

void sotlas_panic(const char *message) {
    (void)message;
    // Laço infinito de parada freestanding para bare-metal / kernel
    for (;;) {
#if defined(__x86_64__) || defined(_M_X64)
        __asm__ volatile ("hlt");
#endif
    }
}

void sotlas_arc_init(SotlasArcHeader *header, size_t size) {
    if (header) {
        header->ref_count = 1;
        header->data_size = size;
    }
}

SotlasArcHeader *sotlas_arc_retain(SotlasArcHeader *header) {
    if (header) {
        header->ref_count++;
    }
    return header;
}

bool sotlas_arc_release(SotlasArcHeader *header) {
    if (header) {
        if (header->ref_count > 0) {
            header->ref_count--;
        }
        return (header->ref_count == 0);
    }
    return false;
}

size_t sotlas_arc_count(const SotlasArcHeader *header) {
    return header ? header->ref_count : 0;
}

void *sotlas_memset(void *dest, int val, size_t count) {
    unsigned char *ptr = (unsigned char *)dest;
    unsigned char b = (unsigned char)val;
    for (size_t i = 0; i < count; i++) {
        ptr[i] = b;
    }
    return dest;
}

void *sotlas_memcpy(void *dest, const void *src, size_t count) {
    unsigned char *d = (unsigned char *)dest;
    const unsigned char *s = (const unsigned char *)src;
    for (size_t i = 0; i < count; i++) {
        d[i] = s[i];
    }
    return dest;
}

int sotlas_memcmp(const void *s1, const void *s2, size_t count) {
    const unsigned char *p1 = (const unsigned char *)s1;
    const unsigned char *p2 = (const unsigned char *)s2;
    for (size_t i = 0; i < count; i++) {
        if (p1[i] < p2[i]) return -1;
        if (p1[i] > p2[i]) return 1;
    }
    return 0;
}
