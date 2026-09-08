import * as path from 'path';
import * as vscode from 'vscode';
import {
    LanguageClient,
    LanguageClientOptions,
    ServerOptions,
    TransportKind
} from 'vscode-languageclient/node';

let client: LanguageClient;

export function activate(context: vscode.ExtensionContext) {
    const config = vscode.workspace.getConfiguration('sotlas');
    const compilerPath = config.get<string>('compilerPath') || 'sotlas';

    // Opções do servidor LSP (invoca 'sotlas lsp --stdio')
    const serverOptions: ServerOptions = {
        command: compilerPath,
        args: ['lsp', '--stdio'],
        transport: TransportKind.stdio
    };

    // Opções do cliente de linguagem
    const clientOptions: LanguageClientOptions = {
        documentSelector: [
            { scheme: 'file', language: 'sotlas' }
        ],
        synchronize: {
            fileEvents: vscode.workspace.createFileSystemWatcher('**/*.sotlas')
        }
    };

    // Cria e inicia o cliente LSP
    client = new LanguageClient(
        'sotlasLanguageServer',
        'Sotlas Language Server',
        serverOptions,
        clientOptions
    );

    client.start();

    // Comandos contribuídos pela extensão
    context.subscriptions.push(
        vscode.commands.registerCommand('sotlas.build', async () => {
            const terminal = vscode.window.createTerminal('Sotlas Build');
            terminal.show();
            terminal.sendText(`${compilerPath} build`);
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('sotlas.check', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;
            const terminal = vscode.window.createTerminal('Sotlas Check');
            terminal.show();
            terminal.sendText(`${compilerPath} check "${editor.document.fileName}"`);
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('sotlas.format', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;
            const terminal = vscode.window.createTerminal('Sotlas Format');
            terminal.show();
            terminal.sendText(`${compilerPath} fmt "${editor.document.fileName}"`);
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('sotlas.studio', async () => {
            const terminal = vscode.window.createTerminal('Sotlas Studio');
            terminal.show();
            terminal.sendText(`${compilerPath} studio`);
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('sotlas.repl', async () => {
            const terminal = vscode.window.createTerminal('Sotlas REPL');
            terminal.show();
            terminal.sendText(`${compilerPath} repl`);
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('sotlas.dumpWasm', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;
            const terminal = vscode.window.createTerminal('Sotlas Wasm');
            terminal.show();
            terminal.sendText(`${compilerPath} compile "${editor.document.fileName}" --emit-wasm`);
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('sotlas.restartServer', async () => {
            if (client) {
                await client.stop();
                client.start();
                vscode.window.showInformationMessage('Servidor Sotlas LSP reiniciado com sucesso.');
            }
        })
    );
}

export function deactivate(): Thenable<void> | undefined {
    if (!client) {
        return undefined;
    }
    return client.stop();
}
