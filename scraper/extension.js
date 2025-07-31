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

			let projectName = getActiveProjectName();
			if (!projectName) {
				vscode.window.showErrorMessage("No active project folder found.");
				return;
			}

			projectName = projectName
				.replace(/[^a-zA-Z0-9._-]/g, '-') // replace invalid characters with '-'
				.replace(/^-+|-+$/g, ''); // remove leading/trailing dashes

			try {
				const res = await axios.post('http://34.216.243.243/semantic/semantic-search', {
					machineId,
					projectName,
					query
				});

				if (res.data.error) {
					vscode.window.showErrorMessage("Search failed: " + res.data.error);
					return;
				}

				const matches = res.data.matches;
				if (!matches || matches.length === 0) {
					vscode.window.showInformationMessage("No relevant results found.");
					return;
				}

				// Persistent QuickPick
				const quickPick = vscode.window.createQuickPick();
				quickPick.items = matches.map((match, index) => ({
					label: `Result ${index + 1}`,
					description: `${match.file_path} : Line ${match.line_number + 1}`,
					detail: `Click to go to this location`,
					match
				}));
				quickPick.title = "Semantic Search Results";
				quickPick.matchOnDescription = true;
				quickPick.matchOnDetail = true;
				quickPick.ignoreFocusOut = true; // Keeps it open when focus changes

				// Handle when user presses enter (doesn't auto-close)
				quickPick.onDidAccept(async () => {
					const picked = quickPick.selectedItems[0];
					if (!picked) return;

					const { file_path, line_number } = picked.match;

					const folderUri = vscode.workspace.workspaceFolders?.[0]?.uri;
					const fileUri = vscode.Uri.joinPath(folderUri, file_path);
					const doc = await vscode.workspace.openTextDocument(fileUri);
					const editor = await vscode.window.showTextDocument(doc);

					const position = new vscode.Position(line_number, 0);
					const range = new vscode.Range(position, position);
					editor.selection = new vscode.Selection(position, position);
					editor.revealRange(range, vscode.TextEditorRevealType.InCenter);

					// ❌ DO NOT call quickPick.hide() or dispose(), keep it open
				});

				// Close only when ESC or click outside
				quickPick.onDidHide(() => quickPick.dispose());

				quickPick.show();

			} catch (err) {
				if (err.code === 'ENOTFOUND' || err.message.includes('awseb') || err.message.includes('getaddrinfo')) {
					vscode.window.showErrorMessage("Backend not live. Please try again later.");
				} else {
					vscode.window.showErrorMessage("Upload failed: " + err.message);
				}		
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
			let projectName = path.basename(rootPath);

			// Sanitize projectName to meet backend validation requirements
			projectName = projectName
				.replace(/[^a-zA-Z0-9._-]/g, '-') // replace invalid characters with '-'
				.replace(/^-+|-+$/g, ''); // remove leading/trailing dashes

			vscode.window.withProgress({
				location: vscode.ProgressLocation.Notification,
				title: "Uploading project to agent, this may take a while...",
				cancellable: true
			}, async (progress) => {
				try {
					const files = [];

					const IGNORED_DIRS = [
						'node_modules', '.git', 'dist', 'build', '.next', '.vscode', '.venv', '__pycache__', 'env', 'target', 'out', 'bin', 'logs'
					];
					const ALLOWED_EXTENSIONS = [
						'.js', '.ts', '.jsx', '.tsx', '.json', '.html', '.py', '.env', '.java', '.xml', '.properties'
					];
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

					await axios.post('http://34.216.243.243/semantic/upload-folder', {
						machineId,
						projectName,
						files
					});

					vscode.window.showInformationMessage("✅ Project uploaded to agent successfully.");
				} catch (err) {
					if (err.code === 'ENOTFOUND' || err.message.includes('awseb') || err.message.includes('getaddrinfo')) {
						vscode.window.showErrorMessage("Backend not live. Please try again later.");
					} else {
						vscode.window.showErrorMessage("Upload failed: " + err.message);
				}
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
					const response = await axios.post('http://34.216.243.243/chat', {
						prompt: text,
						image_base64: image_base64,
						file_context: file_context
					});

					webviewView.webview.postMessage({
						command: 'response',
						text: response.data.reply
					});
				} catch (err) {
					if (err.code === 'ENOTFOUND' || err.message.includes('getaddrinfo')) {
						webviewView.webview.postMessage({
							command: 'response',
							text: 'Backend not live. Please try again later'
						});
					} else{
						webviewView.webview.postMessage({	
							command: 'response',
							text: 'Error: ' + err.message
						});
					}
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
				/* Dark-Themed Chat UI Stylesheet */
				:root {
				/* Theme colors */
				--bg-dark: #0d0d0d;
				--bg-light: #1f1f1f;
				--accent: #274156;
				--accent-dark: #1b2a38;
				--text-primary: #e0e0e0;
				--text-secondary: #777;
				--border: #333;
				--bubble-user: linear-gradient(135deg, #274156 0%, #1b2a38 100%);
				--bubble-bot: rgba(255, 255, 255, 0.08);
				}

				* {
				box-sizing: border-box;
				}

				body {
				font-family: 'Segoe UI', Arial, sans-serif;
				margin: 0;
				padding: 0;
				background: var(--bg-dark);
				color: var(--text-primary);
				height: 100vh;
				display: flex;
				flex-direction: column;
				overflow: hidden;
				}

				/* Chat area */
				#chat {
				flex: 1;
				overflow-y: auto;
				padding: 1.5em;
				background: linear-gradient(to bottom, #121212 0%, #1f1f1f 100%);
				border-bottom: 1px solid var(--border);
				scrollbar-width: thin;
				scrollbar-color: var(--border) transparent;
				}

				#chat::-webkit-scrollbar { width: 8px; }
				#chat::-webkit-scrollbar-track { background: transparent; }
				#chat::-webkit-scrollbar-thumb { background-color: var(--border); border-radius: 4px; }

				/* Message bubbles */
				.message-wrapper {
				display: flex;
				width: 100%;
				margin-bottom: 1em;
				animation: fadeIn 0.4s ease-out;
				}
				.message-wrapper.user { justify-content: flex-end; }
				.message-wrapper.bot { justify-content: flex-start; }

				.bubble {
				position: relative;
				padding: 0.8em 1.4em;
				border-radius: 1.2em;
				box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
				word-break: break-word;
				max-width: 75%;
				width: fit-content;
				background-clip: padding-box;
				transition: transform 0.2s ease, box-shadow 0.2s ease;
				}
				.bubble:hover {
				transform: translateY(-2px);
				box-shadow: 0 6px 16px rgba(0, 0, 0, 0.6);
				}

				.bubble.user {
				background: var(--bubble-user);
				color: #f0f0f0;
				border-bottom-right-radius: 0.4em;
				}
				.bubble.user::after {
				content: "";
				position: absolute;
				bottom: 0;
				right: -8px;
				border-top: 10px solid var(--bubble-user);
				border-left: 10px solid transparent;
				}

				.bubble.bot {
				background: var(--bubble-bot);
				backdrop-filter: blur(8px);
				border: 1px solid var(--border);
				color: var(--text-primary);
				border-bottom-left-radius: 0.4em;
				}
				.bubble.bot::after {
				content: "";
				position: absolute;
				bottom: 0;
				left: -8px;
				border-top: 10px solid var(--bubble-bot);
				border-right: 10px solid transparent;
				}

				/* Input area */
				#input-area {
				display: flex;
				align-items: center;
				padding: 1em;
				background: var(--bg-light);
				border-top: 1px solid var(--border);
				gap: 0.7em;
				transition: background 0.3s;
				}
				#input-area:hover { background: #2a2a2a; }

				#input {
				flex: 1;
				padding: 0.8em 1.2em;
				border-radius: 1em;
				border: 1px solid #555;
				background: #181818;
				color: var(--text-primary);
				outline: none;
				font-size: 1em;
				resize: none;
				min-height: 2.8em;
				max-height: 6em;
				overflow-y: auto;
				line-height: 1.5;
				transition: border-color 0.2s;
				}
				#input:focus { border-color: var(--accent); }

				/* Buttons */
				#imageLabel,
				.file-toggle,
				#send {
				padding: 0.5em 1em;
				border-radius: 1em;
				font-size: 0.9em;
				font-weight: bold;
				cursor: pointer;
				transition: background 0.3s, color 0.3s, transform 0.2s;
				}

				#imageLabel {
				background: linear-gradient(to right, #444, #666);
				color: #fff;
				border: none;
				}
				#imageLabel:hover { transform: scale(1.05); background: linear-gradient(to right, #666, #444); }

				#imageLabel.active {
					background: linear-gradient(45deg, var(--accent-dark), var(--accent));
					color: #fff;
				}

				.file-toggle {
				border: 1px solid #444;
				background: #1f1f1f;
				color: var(--text-secondary);
				}
				.file-toggle:hover,
				.file-toggle.active {
				background: var(--accent);
				color: #fff;
				border: none;
				transform: scale(1.05);
				}

				#send {
				background: linear-gradient(to right, var(--accent), var(--accent-dark));
				color: #fff;
				border: none;
				}
				#send:hover { transform: scale(1.05); background: linear-gradient(to right, var(--accent-dark), var(--accent)); }
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

				/* Code blocks */
				pre, code {
				background: #181818;
				color: #e5e5e5;
				padding: 0.6em;
				border-radius: 6px;
				overflow-x: auto;
				font-family: Consolas, monospace;
				font-size: 0.95em;
				}

				/* Animations */
				@keyframes spin { to { transform: translate(-50%, -50%) rotate(360deg); } }
				@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }

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
				const imageInput = document.getElementById('imageInput');
				const imageLabel = document.getElementById('imageLabel');
				let useCurrentFile = false;

				// Toggle file context
				const fileBtn = document.getElementById("fileContextBtn");
				fileBtn.addEventListener("click", () => {
					useCurrentFile = !useCurrentFile;
					fileBtn.classList.toggle("active", useCurrentFile);
				});

				// Update label when image selected or cleared
				imageInput.addEventListener('change', () => {
					if (imageInput.files.length > 0) {
						imageLabel.classList.add('active');
						imageLabel.textContent = '📁 Uploaded';
					} else {
						imageLabel.classList.remove('active');
						imageLabel.textContent = '📁 Upload';
					}
				});

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

				// Handle send click
				send.onclick = async () => {
					const text = input.value.trim();
					const file = imageInput.files[0];
					if (!text && !file && !useCurrentFile) return;

					const messageWrapper = addMessage(text || '[Image]' || '[File]', 'user');

					// Indicators
					const indicators = [];
					if (file) indicators.push('📁 Image');
					if (useCurrentFile) indicators.push('📄 File');

					if (indicators.length) {
						const meta = document.createElement('div');
						meta.style.fontSize = '0.75em';
						meta.style.color = '#999';
						meta.style.marginTop = '0.2em';
						meta.textContent = indicators.join(' | ');
						messageWrapper.appendChild(meta);
					}

					// Reset input & image
					input.value = '';
					imageInput.value = '';
					imageLabel.classList.remove('active');
					imageLabel.textContent = '📁 Upload';

					send.disabled = true;
					send.classList.add('loading');

					let imageBase64 = null;
					if (file) {
						imageBase64 = await toBase64(file);
					}

					vscode.postMessage({
						command: 'sendPrompt',
						text,
						image_base64: imageBase64,
						use_file: useCurrentFile
					});
				};

				function toBase64(file) {
					return new Promise((resolve, reject) => {
						const reader = new FileReader();
						reader.readAsDataURL(file);
						reader.onload = () => resolve(reader.result);
						reader.onerror = error => reject(error);
					});
				}

				input.addEventListener('keydown', (e) => {
					if (e.key === 'Enter' && !e.shiftKey) {
						e.preventDefault();
						send.onclick();
					}
				});

				window.addEventListener('message', event => {
					const message = event.data;
					if (message.command === 'response') {
						addMessage(message.text, 'bot');
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