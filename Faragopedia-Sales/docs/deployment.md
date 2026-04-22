# Deployment & Setup Guide

This guide covers how to deploy Faragopedia-Sales using Docker, Docker Compose, and Portainer Stacks.

## Environment Variables

The following variables can be configured in your `.env` file or passed as environment variables in Portainer.

### AI Configuration
| Variable | Description | Default |
| :--- | :--- | :--- |
| `AI_PROVIDER` | The LLM provider (`openai`, `anthropic`, `google`, `openrouter`) | `openai` |
| `AI_MODEL` | The specific model to use (e.g., `gpt-4o-mini`, `claude-3-5-sonnet-20240620`) | `gpt-4o-mini` |
| `OPENAI_API_KEY` | Your OpenAI API key | - |
| `ANTHROPIC_API_KEY` | Your Anthropic API key | - |
| `GOOGLE_API_KEY` | Your Google AI (Gemini) API key | - |
| `OPENROUTER_API_KEY` | Your OpenRouter API key | - |

### Deployment & Permissions
These variables are critical for ensuring files created by the AI are accessible on your host machine.

| Variable | Description | Recommended |
| :--- | :--- | :--- |
| `DATA_DIR` | Absolute path on your host to store the wiki and sources. | `/home/user/docker/faragopedia` |
| `PUID` | The User ID of your host user (run `id -u` to find it). | `1000` |
| `PGID` | The Group ID of your host user (run `id -g` to find it). | `1000` |
| `BACKEND_PORT` | The host port for the FastAPI backend. | `8300` |
| `FRONTEND_PORT` | The host port for the React frontend. | `5173` |

### Web & Networking
| Variable | Description | Default |
| :--- | :--- | :--- |
| `VITE_API_BASE_URL` | The URL the frontend uses to contact the backend. | `http://localhost:8300` |
| `VITE_ALLOWED_HOST` | Allowed hostname for the frontend. | `localhost` |
| `WISECRAWLER_BASE_URL`| (Optional) URL for a WiseCrawler instance for web scraping. | - |
| `WISECRAWLER_API_KEY` | (Optional) API key for WiseCrawler. | - |

---

## Deployment Options

### 1. Local Docker Compose
Best for local development or individual use.

1. Clone the repo: `git clone https://github.com/accountantwise/Faragopedia-Sales.git`
2. Create your `.env` file from the example.
3. Run `docker-compose up -d`.
4. Access at `http://localhost:5173`.

### 2. Portainer Stacks (Recommended for Self-Hosting)
Best for persistent deployments on a server.

1. In Portainer, create a new **Stack**.
2. Select **Repository** and enter the Git URL.
3. In the **Environment Variables** section, add the variables listed above.
   - **Crucial**: Set `DATA_DIR` to a permanent path on your server (e.g., `/home/colacho/docker/faragopedia`).
   - Set `PUID` and `PGID` so you can manage the markdown files directly via SFTP/SMB.
4. Deploy the stack.

---

## Permissions Troubleshooting

If you see "Permission Denied" errors in the logs:
1. Ensure the directory you pointed `DATA_DIR` to exists on the host.
2. Ensure that directory is owned by the user matching your `PUID`/`PGID`.
   ```bash
   sudo chown -R 1000:1000 /your/data/path
   ```
