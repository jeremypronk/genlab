// The module 'vscode' contains the VS Code extensibility API
// Import the module and reference it with the alias vscode in your code below
import * as vscode from 'vscode';
import * as path from 'path';

function runPythonScript(uri: vscode.Uri, scriptArg: string) {
    if (!uri || !uri.fsPath) {
        vscode.window.showErrorMessage('No file selected!');
        return;
    }
    
    const filePath = uri.fsPath;
    const fileDirectory = path.dirname(filePath);

    // genlab command
    const commandToRun = `genlab ${scriptArg} "${filePath}"`;

    const terminal = vscode.window.createTerminal({
        name: `GenLab: ${scriptArg}`, // Names the terminal based on the arg
        cwd: fileDirectory
    });

    terminal.show();
    terminal.sendText(commandToRun);
}


// This method is called when your extension is activated
// Your extension is activated the very first time the command is executed
export function activate(context: vscode.ExtensionContext) {

	// Use the console to output diagnostic information (console.log) and errors (console.error)
	// This line of code will only be executed once when your extension is activated
	console.log('Congratulations, your extension "genlab-ext" is now active!');

    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_image_nano_banana_pro_t2i_2K_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type image --model nano-banana-pro-t2i-2K --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_image_nano_banana_pro_t2i_2K_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type image --model nano-banana-pro-t2i-2K --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_image_nano_banana_pro_t2i_2K_x4', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type image --model nano-banana-pro-t2i-2K --generations 4');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_image_nano_banana_pro_t2i_2K_x6', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type image --model nano-banana-pro-t2i-2K --generations 6');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_image_nano_banana_pro_t2i_2K_x10', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type image --model nano-banana-pro-t2i-2K --generations 10');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_image_nano_banana_pro_t2i_4K_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type image --model nano-banana-pro-t2i-4K --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_image_nano_banana_pro_t2i_4K_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type image --model nano-banana-pro-t2i-4K --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_image_nano_banana_pro_t2i_4K_x4', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type image --model nano-banana-pro-t2i-4K --generations 4');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_image_nano_banana_pro_t2i_4K_x6', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type image --model nano-banana-pro-t2i-4K --generations 6');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_image_nano_banana_pro_t2i_4K_x10', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type image --model nano-banana-pro-t2i-4K --generations 10');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_image_nano_banana_pro_i2i_2K_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type image --model nano-banana-pro-i2i-2K --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_image_nano_banana_pro_i2i_2K_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type image --model nano-banana-pro-i2i-2K --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_image_nano_banana_pro_i2i_2K_x4', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type image --model nano-banana-pro-i2i-2K --generations 4');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_image_nano_banana_pro_i2i_2K_x6', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type image --model nano-banana-pro-i2i-2K --generations 6');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_image_nano_banana_pro_i2i_2K_x10', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type image --model nano-banana-pro-i2i-2K --generations 10');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_image_nano_banana_pro_i2i_4K_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type image --model nano-banana-pro-i2i-4K --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_image_nano_banana_pro_i2i_4K_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type image --model nano-banana-pro-i2i-4K --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_image_nano_banana_pro_i2i_4K_x4', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type image --model nano-banana-pro-i2i-4K --generations 4');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_image_nano_banana_pro_i2i_4K_x6', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type image --model nano-banana-pro-i2i-4K --generations 6');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_image_nano_banana_pro_i2i_4K_x10', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type image --model nano-banana-pro-i2i-4K --generations 10');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_gpt_image_2_5_sunburst_t2i_2K_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type gpt-image --model 2.5-sunburst-t2i-2K --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_gpt_image_2_5_sunburst_t2i_2K_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type gpt-image --model 2.5-sunburst-t2i-2K --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_gpt_image_2_5_sunburst_t2i_2K_x4', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type gpt-image --model 2.5-sunburst-t2i-2K --generations 4');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_gpt_image_2_5_sunburst_t2i_2K_x6', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type gpt-image --model 2.5-sunburst-t2i-2K --generations 6');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_gpt_image_2_5_sunburst_t2i_2K_x10', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type gpt-image --model 2.5-sunburst-t2i-2K --generations 10');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_gpt_image_2_5_sunburst_t2i_4K_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type gpt-image --model 2.5-sunburst-t2i-4K --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_gpt_image_2_5_sunburst_t2i_4K_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type gpt-image --model 2.5-sunburst-t2i-4K --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_gpt_image_2_5_sunburst_t2i_4K_x4', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type gpt-image --model 2.5-sunburst-t2i-4K --generations 4');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_gpt_image_2_5_sunburst_t2i_4K_x6', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type gpt-image --model 2.5-sunburst-t2i-4K --generations 6');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_gpt_image_2_5_sunburst_t2i_4K_x10', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type gpt-image --model 2.5-sunburst-t2i-4K --generations 10');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_gpt_image_2_5_sunburst_i2i_2K_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type gpt-image --model 2.5-sunburst-i2i-2K --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_gpt_image_2_5_sunburst_i2i_2K_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type gpt-image --model 2.5-sunburst-i2i-2K --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_gpt_image_2_5_sunburst_i2i_2K_x4', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type gpt-image --model 2.5-sunburst-i2i-2K --generations 4');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_gpt_image_2_5_sunburst_i2i_2K_x6', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type gpt-image --model 2.5-sunburst-i2i-2K --generations 6');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_gpt_image_2_5_sunburst_i2i_2K_x10', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type gpt-image --model 2.5-sunburst-i2i-2K --generations 10');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_gpt_image_2_5_sunburst_i2i_4K_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type gpt-image --model 2.5-sunburst-i2i-4K --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_gpt_image_2_5_sunburst_i2i_4K_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type gpt-image --model 2.5-sunburst-i2i-4K --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_gpt_image_2_5_sunburst_i2i_4K_x4', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type gpt-image --model 2.5-sunburst-i2i-4K --generations 4');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_gpt_image_2_5_sunburst_i2i_4K_x6', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type gpt-image --model 2.5-sunburst-i2i-4K --generations 6');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_gpt_image_2_5_sunburst_i2i_4K_x10', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type gpt-image --model 2.5-sunburst-i2i-4K --generations 10');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_i2v_480p_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-i2v-480p --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_i2v_480p_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-i2v-480p --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_i2v_480p_x3', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-i2v-480p --generations 3');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_i2v_720p_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-i2v-720p --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_i2v_720p_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-i2v-720p --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_i2v_720p_x3', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-i2v-720p --generations 3');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_i2v_1080p_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-i2v-1080p --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_i2v_1080p_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-i2v-1080p --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_i2v_1080p_x3', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-i2v-1080p --generations 3');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_fast_i2v_480p_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-fast-i2v-480p --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_fast_i2v_480p_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-fast-i2v-480p --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_fast_i2v_480p_x3', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-fast-i2v-480p --generations 3');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_fast_i2v_720p_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-fast-i2v-720p --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_fast_i2v_720p_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-fast-i2v-720p --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_fast_i2v_720p_x3', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-fast-i2v-720p --generations 3');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_fflf_480p_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-fflf-480p --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_fflf_480p_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-fflf-480p --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_fflf_480p_x3', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-fflf-480p --generations 3');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_fflf_720p_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-fflf-720p --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_fflf_720p_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-fflf-720p --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_fflf_720p_x3', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-fflf-720p --generations 3');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_fflf_1080p_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-fflf-1080p --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_fflf_1080p_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-fflf-1080p --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_fflf_1080p_x3', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-fflf-1080p --generations 3');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_fast_fflf_480p_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-fast-fflf-480p --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_fast_fflf_480p_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-fast-fflf-480p --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_fast_fflf_480p_x3', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-fast-fflf-480p --generations 3');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_fast_fflf_720p_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-fast-fflf-720p --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_fast_fflf_720p_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-fast-fflf-720p --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_fast_fflf_720p_x3', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-fast-fflf-720p --generations 3');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_5_i2v_480p_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.5-i2v-480p --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_5_i2v_480p_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.5-i2v-480p --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_5_i2v_480p_x3', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.5-i2v-480p --generations 3');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_5_i2v_720p_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.5-i2v-720p --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_5_i2v_720p_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.5-i2v-720p --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_5_i2v_720p_x3', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.5-i2v-720p --generations 3');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_5_fflf_480p_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.5-fflf-480p --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_5_fflf_480p_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.5-fflf-480p --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_5_fflf_480p_x3', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.5-fflf-480p --generations 3');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_5_fflf_720p_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.5-fflf-720p --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_5_fflf_720p_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.5-fflf-720p --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_5_fflf_720p_x3', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.5-fflf-720p --generations 3');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_kling_2_1_i2v_std_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type kling --model 2.1-i2v-std --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_kling_2_1_i2v_std_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type kling --model 2.1-i2v-std --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_kling_2_1_i2v_std_x3', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type kling --model 2.1-i2v-std --generations 3');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_kling_2_5_turbo_i2v_pro_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type kling --model 2.5-turbo-i2v-pro --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_kling_2_5_turbo_i2v_pro_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type kling --model 2.5-turbo-i2v-pro --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_kling_2_5_turbo_i2v_pro_x3', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type kling --model 2.5-turbo-i2v-pro --generations 3');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_kling_3_0_i2v_std_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type kling --model 3.0-i2v-std --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_kling_3_0_i2v_std_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type kling --model 3.0-i2v-std --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_kling_3_0_i2v_std_x3', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type kling --model 3.0-i2v-std --generations 3');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_kling_3_0_i2v_pro_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type kling --model 3.0-i2v-pro --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_kling_3_0_i2v_pro_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type kling --model 3.0-i2v-pro --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_kling_3_0_i2v_pro_x3', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type kling --model 3.0-i2v-pro --generations 3');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_kling_3_0_i2v_4K_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type kling --model 3.0-i2v-4K --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_kling_3_0_i2v_4K_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type kling --model 3.0-i2v-4K --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_kling_3_0_i2v_4K_x3', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type kling --model 3.0-i2v-4K --generations 3');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_kling_3_0_fflf_std_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type kling --model 3.0-fflf-std --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_kling_3_0_fflf_std_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type kling --model 3.0-fflf-std --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_kling_3_0_fflf_std_x3', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type kling --model 3.0-fflf-std --generations 3');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_kling_3_0_fflf_pro_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type kling --model 3.0-fflf-pro --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_kling_3_0_fflf_pro_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type kling --model 3.0-fflf-pro --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_kling_3_0_fflf_pro_x3', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type kling --model 3.0-fflf-pro --generations 3');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_kling_3_0_fflf_4K_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type kling --model 3.0-fflf-4K --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_kling_3_0_fflf_4K_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type kling --model 3.0-fflf-4K --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_kling_3_0_fflf_4K_x3', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type kling --model 3.0-fflf-4K --generations 3');
    }));

}

// This method is called when your extension is deactivated
export function deactivate() {}
