const vscode = require('vscode');
const axios = require('axios'); // Add axios to your dependencies
/**
 * @param {vscode.ExtensionContext} context
 */
function activate(context) {

	console.log('Congratulations, your extension "scraper" is now active!');

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
}

class ScraperChatViewProvider {
	constructor(context) {
		this.context = context;
	}

	resolveWebviewView(webviewView) {
		webviewView.webview.options = {
			enableScripts: true
		};

		webviewView.webview.html = getWebviewContent();

		// Handle messages from the webview
		webviewView.webview.onDidReceiveMessage(async (message) => {
			if (message.command === 'sendPrompt') {
				const prompt = message.text;
				try {
					const response = await axios.post('http://localhost:8000/chat', { prompt });
					webviewView.webview.postMessage({ command: 'response', text: response.data.reply });
				} catch (err) {
					webviewView.webview.postMessage({ command: 'response', text: 'Error: ' + err.message });
				}
			}
		});
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
					background: linear-gradient(135deg, #0ff 0%, #00f 100%);
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
					padding: 0.8em;
					background: #1b1b1b;
					border-top: 1px solid #333;
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
				}

				#send {
					margin-left: 0.7em;
					padding: 0.6em 1.5em;
					border-radius: 1em;
					border: none;
					background: linear-gradient(to right, #00c6ff, #0072ff);
					color: #fff;
					font-weight: bold;
					cursor: pointer;
					transition: background 0.3s ease;
				}

				#send:hover {
					background: linear-gradient(to right, #0072ff, #00c6ff);
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
				<input id="input" type="text" placeholder="Type your prompt..." autocomplete="off" />
				<button id="send">Send</button>
			</div>
			<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
			<script>
				const vscode = acquireVsCodeApi();
				const chat = document.getElementById('chat');
				const input = document.getElementById('input');
				const send = document.getElementById('send');

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

				send.onclick = () => {
					const text = input.value.trim();
					if (text) {
						addMessage(text, 'user');
						input.value = '';
						send.disabled = true;

						// Add processing placeholder message from bot
						processingDiv = addMessage('_Processing request..._', 'bot');

						vscode.postMessage({ command: 'sendPrompt', text });
					}
				};
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
