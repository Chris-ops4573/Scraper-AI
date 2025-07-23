const vscode = require('vscode');
const axios = require('axios'); // Add axios to your dependencies
const fs = require('fs');
const path = require('path');
/**
 * @param {vscode.ExtensionContext} context
 */
function activate(context) {

	console.log('Congratulations, your extension "scraper" is now active!');

	const machineId = vscode.env.machineId;

	const disposable = vscode.commands.registerCommand('scraper.scrapeForCode', function () {
		vscode.window.showInformationMessage('Hello World from scraper!');
	});

	context.subscriptions.push(disposable);

	// Register the webview view provider
	context.subscriptions.push(
		vscode.window.registerWebviewViewProvider(
			'scraper.chatView',
			new ScraperChatViewProvider(context)
		)
	);

	const getActiveProjectName = () => {
	const folders = vscode.workspace.workspaceFolders;
	if (!folders || folders.length === 0) return null;
	return path.basename(folders[0].uri.fsPath);
};

	context.subscriptions.push(
		vscode.commands.registerCommand('scraper.semanticSearch', async () => {
			const query = await vscode.window.showInputBox({
				prompt: "What are you looking for?",
				placeHolder: "e.g. login validation, error handling middleware"
			});

			if (!query) return;

			const projectName = getActiveProjectName();
			if (!projectName) {
				vscode.window.showErrorMessage("No active project folder found.");
				return;
			}

			try {
				const res = await axios.post('http://localhost:8000/semantic/semantic-search', {
					machineId,
					projectName,
					query
				});

				const { file_path, line_number } = res.data;

				const folderUri = vscode.workspace.workspaceFolders?.[0]?.uri;
				const fileUri = vscode.Uri.joinPath(folderUri, file_path);
				const doc = await vscode.workspace.openTextDocument(fileUri);

				const editor = await vscode.window.showTextDocument(doc);

				const position = new vscode.Position(line_number, 0);
				const range = new vscode.Range(position, position);

				editor.selection = new vscode.Selection(position, position);
				editor.revealRange(range, vscode.TextEditorRevealType.InCenter);
			} catch (err) {
				vscode.window.showErrorMessage("Search failed: " + err.message);
			}
		})
	);

	context.subscriptions.push(
		vscode.commands.registerCommand('scraper.uploadProjectToAgent', async () => {
			const folders = vscode.workspace.workspaceFolders;
			if (!folders || folders.length === 0) {
				vscode.window.showErrorMessage("No folder is open in VS Code.");
				return;
			}

			const rootPath = folders[0].uri.fsPath;
			const projectName = path.basename(rootPath);

			vscode.window.withProgress({
				location: vscode.ProgressLocation.Notification,
				title: "Uploading project to agent, this may take a while...",
				cancellable: true
			}, async (progress) => {
				try {
					const files = [];

					const IGNORED_DIRS = ['node_modules', '.git', 'dist', 'build', '.next', '.vscode'];
					const ALLOWED_EXTENSIONS = ['.js', '.ts', '.jsx', '.tsx', '.json', '.html', '.py', '.env', '.md'];
					const MAX_FILE_SIZE = 2 * 1024 * 1024; // 2 MB

					function shouldIncludeFile(filePath) {
						const ext = path.extname(filePath);
						const baseName = path.basename(filePath);
						return (
							(baseName === 'package.json' || baseName === '.env') ||
							(ALLOWED_EXTENSIONS.includes(ext) && baseName !== 'package-lock.json')
						);

					}

					function readFilesRecursively(dir, files) {
						const entries = fs.readdirSync(dir, { withFileTypes: true });

						for (const entry of entries) {
							const fullPath = path.join(dir, entry.name);
							const relativePath = path.relative(vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '', fullPath);

							if (entry.isDirectory() && IGNORED_DIRS.includes(entry.name)) continue;

							if (entry.isDirectory()) {
								readFilesRecursively(fullPath, files);
							} else if (entry.isFile()) {
								if (shouldIncludeFile(fullPath)) {
									const stats = fs.statSync(fullPath);
									if (stats.size < MAX_FILE_SIZE) {
										const content = fs.readFileSync(fullPath, 'utf-8');
										files.push({ path: relativePath, content });
									}
								}
							}
						}
					}

					readFilesRecursively(rootPath, files);

					await axios.post('http://localhost:8000/semantic/upload-folder', {
						machineId,
						projectName,
						files
					});

					vscode.window.showInformationMessage("✅ Project uploaded to agent successfully.");
				} catch (err) {
					vscode.window.showErrorMessage("Upload failed: " + err.message);
				}
			});
		})
	);
}

class ScraperChatViewProvider {
	constructor(context) {
		this.context = context;
	}

	resolveWebviewView(webviewView) {
		webviewView.webview.options = {
			enableScripts: true
		};

		webviewView.webview.onDidReceiveMessage(async (message) => {
			if (message.command === 'sendPrompt') {
				let { text, image_base64, use_file } = message;
				let file_context = null;

				if (use_file) {
					const activeEditor = vscode.window.activeTextEditor;
					if (activeEditor) {
						file_context = activeEditor.document.getText();
					}
				}

				try {
					const response = await axios.post('http://localhost:8000/chat', {
						prompt: text,
						image_base64: image_base64,
						file_context: file_context
					});

					webviewView.webview.postMessage({
						command: 'response',
						text: response.data.reply
					});
				} catch (err) {
					webviewView.webview.postMessage({
						command: 'response',
						text: 'Error: ' + err.message
					});
				}
			}
		});

		webviewView.webview.html = getWebviewContent();
	}
}

function getWebviewContent() {
	return `
		<!DOCTYPE html>
		<html lang="en">
		<head>
			<meta charset="UTF-8">
			<style>
				body {
					font-family: 'Segoe UI', Arial, sans-serif;
					margin: 0;
					padding: 0;
					background: #0f0f0f;
					color: #e0e0e0;
					height: 100vh;
					display: flex;
					flex-direction: column;
				}

				#chat {
					flex: 1;
					overflow-y: auto;
					padding: 1em;
					background: linear-gradient(to bottom, #121212, #1a1a1a);
					border-bottom: 1px solid #333;
				}

				.message-wrapper {
					display: flex;
					width: 100%;
					margin-bottom: 0.7em;
					animation: fadeIn 0.3s ease-in-out;
				}

				.message-wrapper.user {
					justify-content: flex-end;
				}

				.message-wrapper.bot {
					justify-content: flex-start;
				}

				.bubble {
					display: inline-block;
					padding: 0.7em 1.2em;
					border-radius: 1.3em;
					box-shadow: 0 3px 10px rgba(0, 0, 0, 0.4);
					word-break: break-word;
					max-width: 70%;
					white-space: pre-wrap;
					width: fit-content;
					transition: all 0.3s ease;
				}

				.bubble.user {
					background: linear-gradient(135deg, #007acc 0%, #005ea6 100%);
					color: #fff;
					text-align: left;
				}

				.bubble.bot {
					background: rgba(255, 255, 255, 0.05);
					backdrop-filter: blur(6px);
					border: 1px solid rgba(255, 255, 255, 0.1);
					color: #dcdcdc;
					text-align: left;
				}

				#input-area {
					display: flex;
					align-items: center; /* NEW: aligns children vertically in center */
					padding: 0.8em;
					background: #1b1b1b;
					border-top: 1px solid #333;
					gap: 0.5em; /* optional: space between elements */
				}

				#input {
					flex: 1;
					padding: 0.7em 1em;
					border-radius: 1em;
					border: 1px solid #555;
					background: #121212;
					color: #d4d4d4;
					outline: none;
					font-size: 1em;
					resize: none;
					min-height: 2.5em;
					max-height: 5em;
					overflow-y: auto;
					line-height: 1.4;
				}

				#imageLabel,
				.file-toggle,
				#send {
					padding: 0.4em 0.8em;
					min-width: auto;
					border-radius: 0.9em;
					font-size: 0.9em;
					font-weight: bold;
					white-space: nowrap;
					cursor: pointer;
					transition: background 0.3s, color 0.3s;
				}

				#imageLabel {
					background: linear-gradient(to right, #444, #666);
					color: #fff;
					border: none;
				}

				#imageLabel:hover {
					background: linear-gradient(to right, #666, #444);
				}

				.file-toggle {
					border: 1px solid #444;
					background: #1f1f1f;
					color: #ccc;
				}

				.file-toggle:hover {
					background: #292929;
				}

				.file-toggle.active {
					background: linear-gradient(to right, #00c6ff, #0072ff);
					color: white;
					border: none;
				}

				#send {
					background: linear-gradient(to right, #00c6ff, #0072ff);
					color: #fff;
					border: none;
				}

				#send:hover {
					background: linear-gradient(to right, #0072ff, #00c6ff);
				}

				#send.loading {
					position: relative;
					color: transparent;
					pointer-events: none;
				}

				#send.loading::after {
					content: '';
					position: absolute;
					top: 50%;
					left: 50%;
					transform: translate(-50%, -50%);
					width: 16px;
					height: 16px;
					border: 2px solid rgba(255, 255, 255, 0.6);
					border-top: 2px solid white;
					border-radius: 50%;
					animation: spin 0.6s linear infinite;
				}

				@keyframes spin {
					0% { transform: translate(-50%, -50%) rotate(0deg); }
					100% { transform: translate(-50%, -50%) rotate(360deg); }
				}

				pre, code {
					background: #121212;
					color: #eee;
					padding: 0.5em;
					border-radius: 6px;
					overflow-x: auto;
					font-family: Consolas, monospace;
					font-size: 0.9em;
				}

				/* Animation */
				@keyframes fadeIn {
					from { opacity: 0; transform: translateY(4px); }
					to { opacity: 1; transform: translateY(0); }
				}

			</style>
		</head>
		<body>
			<div id="chat"></div>
			<div id="input-area">
				<textarea id="input" placeholder="Type your prompt..." autocomplete="off"></textarea>
				<input type="file" id="imageInput" accept="image/*" hidden />
				<label for="imageInput" id="imageLabel">📁 Upload</label>
				<button id="fileContextBtn" class="file-toggle">📄 File</button>
				<button id="send">Send</button>
			</div>
			<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
			<script>
				const vscode = acquireVsCodeApi();
				const chat = document.getElementById('chat');
				const input = document.getElementById('input');
				const send = document.getElementById('send');
				let useCurrentFile = false;

				const fileBtn = document.getElementById("fileContextBtn");
				fileBtn.addEventListener("click", () => {
					useCurrentFile = !useCurrentFile;
					fileBtn.classList.toggle("active", useCurrentFile);
				});	

				let processingDiv = null;

				function addMessage(text, sender) {
					const wrapper = document.createElement('div');
					wrapper.className = 'message-wrapper ' + sender;
					const div = document.createElement('div');
					div.className = 'bubble ' + sender;
					div.innerHTML = sender === 'bot' ? marked.parse(text) : text;
					wrapper.appendChild(div);
					chat.appendChild(wrapper);
					chat.scrollTop = chat.scrollHeight;
					return div;
				}

				window.addEventListener('paste', async (e) => {
					const clipboardItems = e.clipboardData.items;
					for (let i = 0; i < clipboardItems.length; i++) {
						const item = clipboardItems[i];
						if (item.type.indexOf('image') !== -1) {
							const file = item.getAsFile();
							const imageInput = document.getElementById('imageInput');
							const dataTransfer = new DataTransfer();
							dataTransfer.items.add(file);
							imageInput.files = dataTransfer.files;

							const info = document.createElement("div");
							info.textContent = "📋 Image pasted from clipboard";
							info.style.fontSize = "0.8em";
							info.style.color = "#999";
							chat.appendChild(info);
							chat.scrollTop = chat.scrollHeight;
						}
					}
				});

				send.onclick = async () => {
					const text = input.value.trim();
					const imageInput = document.getElementById('imageInput');
					const file = imageInput.files[0];
					let imageBase64 = null;
					let fileContent = null;

					if (!text && !file && !useCurrentFile) return;

					const messageWrapper = addMessage(text || "[Image uploaded]" || "[File context attached]", 'user');

					const indicators = [];
					if (file) indicators.push("📁 Image attached");
					if (useCurrentFile) indicators.push("📄 File context attached");

					if (indicators.length > 0) {
						const meta = document.createElement("div");
						meta.style.fontSize = "0.75em";
						meta.style.color = "#999";
						meta.style.marginTop = "0.2em";
						meta.textContent = indicators.join(" | ");
						messageWrapper.appendChild(meta);
					}

					input.value = '';
					imageInput.value = '';
					
					send.disabled = true;
					send.classList.add('loading');

					if (file) {
						imageBase64 = await toBase64(file);
					}

					try {
						vscode.postMessage({
							command: 'sendPrompt',
							text,
							image_base64: imageBase64,
							use_file: useCurrentFile
						});	
					} catch (err) {
						processingDiv.innerHTML = "Error: " + err.message;
					}
					send.disabled = false;
					useCurrentFile = false; // reset toggle
					fileBtn.classList.toggle("active", useCurrentFile);
				};

				// Convert file to base64
				function toBase64(file) {
					return new Promise((resolve, reject) => {
						const reader = new FileReader();
						reader.readAsDataURL(file);
						reader.onload = () => resolve(reader.result);
						reader.onerror = error => reject(error);
					});
				}
				
				input.addEventListener('keydown', (e) => {
					if (e.key === 'Enter') send.onclick();
				});

				window.addEventListener('message', event => {
					const message = event.data;
					if (message.command === 'response') {
						if (processingDiv) {
							processingDiv.innerHTML = marked.parse(message.text);
							processingDiv = null;
						} else {
							addMessage(message.text, 'bot');
						}
						send.disabled = false;
						send.classList.remove('loading');
					}
				});
			</script>
		</body>
	</html>
	`;
}

// This method is called when your extension is deactivated
function deactivate() {}

module.exports = {
	activate,
	deactivate
}

