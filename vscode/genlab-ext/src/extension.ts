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

async function processFileIncrement(uri: vscode.Uri, mode: 'take' | 'version') {
    if (!uri) {
        vscode.window.showErrorMessage('No file selected.');
        return;
    }

    // Isolate directory and filename
    const filePath = uri.path;
    const lastSlashIndex = filePath.lastIndexOf('/');
    const dir = filePath.substring(0, lastSlashIndex);
    const fileName = filePath.substring(lastSlashIndex + 1);

    // Enforce .genlab file extension
    if (!fileName.toLowerCase().endsWith('.genlab')) {
        vscode.window.showWarningMessage('Increment commands only work on .genlab files.');
        return;
    }

    const regex = /^(.*)(tk)(\d+)(.*?v)(\d+)(.*)$/i;
    const match = fileName.match(regex);

    if (!match) {
        vscode.window.showErrorMessage('Filename does not match the expected tkXXXvYY format.');
        return;
    }

    const [ , prefix, tkStr, takeNumStr, vSeparatorStr, versionNumStr, suffix ] = match;
    const currentTakeNum = parseInt(takeNumStr, 10);

    let maxTake = currentTakeNum;
    let maxVersion = parseInt(versionNumStr, 10);

    // Scan the directory for existing files to find the highest take/version
    try {
        const dirUri = uri.with({ path: dir });
        const files = await vscode.workspace.fs.readDirectory(dirUri);

        for (const [fName, fType] of files) {
            // Only look at files (ignore folders)
            if (fType === vscode.FileType.File) {
                const fMatch = fName.match(regex);

                if (fMatch) {
                    const [ , fPrefix, , fTakeStr, , fVersionStr, fSuffix ] = fMatch;

                    // Ensure the file belongs to the same asset/sequence family
                    if (fPrefix === prefix && fSuffix.toLowerCase() === suffix.toLowerCase()) {
                        const fTakeNum = parseInt(fTakeStr, 10);
                        const fVersionNum = parseInt(fVersionStr, 10);

                        if (mode === 'take') {
                            // Track the highest take overall
                            if (fTakeNum > maxTake) {
                                maxTake = fTakeNum;
                            }
                        } else if (mode === 'version') {
                            // Track the highest version ONLY within the current take
                            if (fTakeNum === currentTakeNum && fVersionNum > maxVersion) {
                                maxVersion = fVersionNum;
                            }
                        }
                    }
                }
            }
        }
    } catch (error: any) {
        vscode.window.showErrorMessage(`Failed to read directory: ${error.message}`);
        return;
    }

    let nextTake: number;
    let nextVersion: number;

    if (mode === 'take') {
        // Increment highest take found, reset version to 1
        nextTake = maxTake + 1;
        nextVersion = 1;
    } else {
        // Keep current take, increment highest version found
        nextTake = currentTakeNum;
        nextVersion = maxVersion + 1;
    }

    // Format new strings with original padding lengths
    const newTakeNumStr = nextTake.toString().padStart(takeNumStr.length, '0');
    const newVersionNumStr = nextVersion.toString().padStart(versionNumStr.length, '0');

    // Construct new filename and URI
    const newFileName = `${prefix}${tkStr}${newTakeNumStr}${vSeparatorStr}${newVersionNumStr}${suffix}`;
    const newUri = uri.with({ path: `${dir}/${newFileName}` });

    try {
        // Copy the file
        await vscode.workspace.fs.copy(uri, newUri, { overwrite: false });
        vscode.window.showInformationMessage(`Created: ${newFileName}`);
    } catch (error: any) {
        if (error.code === 'EntryExists') {
            vscode.window.showErrorMessage(`File ${newFileName} already exists!`);
        } else {
            vscode.window.showErrorMessage(`Failed to increment file: ${error.message}`);
        }
    }
}


// This method is called when your extension is activated
// Your extension is activated the very first time the command is executed
export function activate(context: vscode.ExtensionContext) {

	// Use the console to output diagnostic information (console.log) and errors (console.error)
	// This line of code will only be executed once when your extension is activated
	console.log('Congratulations, your extension "genlab-ext" is now active!');

    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.Increment_version', async (uri: vscode.Uri) => {
        await processFileIncrement(uri, 'version');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.Increment_take', async (uri: vscode.Uri) => {
        await processFileIncrement(uri, 'take');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_task_download', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --download');
    }));
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
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_ref_480p_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-ref-480p --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_ref_480p_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-ref-480p --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_ref_480p_x3', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-ref-480p --generations 3');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_ref_720p_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-ref-720p --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_ref_720p_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-ref-720p --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_ref_720p_x3', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-ref-720p --generations 3');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_fast_ref_480p_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-fast-ref-480p --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_fast_ref_480p_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-fast-ref-480p --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_fast_ref_480p_x3', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-fast-ref-480p --generations 3');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_fast_ref_720p_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-fast-ref-720p --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_fast_ref_720p_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-fast-ref-720p --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_0_fast_ref_720p_x3', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.0-fast-ref-720p --generations 3');
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
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_5_ref_480p_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.5-ref-480p --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_5_ref_480p_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.5-ref-480p --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_5_ref_480p_x3', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.5-ref-480p --generations 3');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_5_ref_720p_x1', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.5-ref-720p --generations 1');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_5_ref_720p_x2', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.5-ref-720p --generations 2');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('scriptRunner.cmd.kieai_seedance_2_5_ref_720p_x3', (uri: vscode.Uri) => {
        runPythonScript(uri, '--api kieai --type seedance --model 2.5-ref-720p --generations 3');
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
