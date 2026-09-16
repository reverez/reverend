# RunPod Development Foundry

This document describes how to set up a Reverend development environment on a fresh RunPod GPU Pod.

## Overview

The RunPod development foundry provides a bootstrap system that transforms a fresh RunPod GPU Pod into a fully functional Reverend AI-assisted coding workstation with minimal manual setup. The system is designed to be safe, idempotent, and reproducible.

## Prerequisites

1. A RunPod PyTorch Pod with CUDA support
2. Persistent `/workspace` storage attached to the Pod
3. SSH access to the Pod
4. GitHub account with appropriate permissions

## Bootstrap Process

### 1. Pod Setup

1. Create a new RunPod PyTorch Pod:
   - Select the official PyTorch image
   - Attach persistent `/workspace` storage 
   - Add your SSH public key for access
   - Launch the Pod

2. Access the Pod via SSH:
   ```bash
   ssh user@pod-ip-address
   ```

### 2. Run Bootstrap

Execute the bootstrap script:

```bash
cd /workspace
curl -fsSL https://raw.githubusercontent.com/reverend-labs/reverend/main/scripts/dev/bootstrap-runpod.sh | bash
```

The bootstrap process will:
- Validate CUDA and GPU availability 
- Check workspace persistence
- Install required development tools
- Clone/retrieve the Reverend repository
- Set up Python environment
- Install Ollama with specified model
- Install OpenCode
- Perform final validation

### 3. GitHub Authentication

The script will prompt you to authenticate with GitHub CLI (`gh auth login`) if not already authenticated.

## Environment Configuration

The bootstrap script accepts several environment variables:

- `ALLOW_EPHEMERAL_WORKSPACE=1` - Allow using ephemeral workspace (not recommended)
- `REVEREND_MODEL=qwen3-coder:30b` - Ollama model to use
- `REVEREND_CONTEXT_LENGTH=65536` - Context window size for the model
- `SKIP_MODEL_PULL=1` - Skip pulling the model if already present
- `SKIP_TESTS=1` - Skip test execution during bootstrap
- `OLLAMA_HOST=localhost` - Ollama host (default: localhost)

## Safety Features

### CUDA Validation

The bootstrap performs strict CUDA validation before any expensive setup:
- Checks that `nvidia-smi` detects GPUs
- Tests actual PyTorch CUDA initialization using system Python 
- Fails immediately if CUDA cannot properly initialize

### Workspace Protection

- Automatically detects if `/workspace` is ephemeral (tmpfs)
- Prominently warns about data loss when using ephemeral storage without explicit override
- Requires `ALLOW_EPHEMERAL_WORKSPACE=1` to proceed with ephemeral storage

### Idempotency

The script is designed to be run multiple times safely:
- Existing installations are preserved
- No destructive operations occur on repeated runs
- Progress updates clearly indicate what's happening

## Persistent Directories

The following directories are created and maintained persistently:

- `/workspace/reverend` - Reverend source code repository
- `/workspace/worktrees` - Git worktrees for development 
- `/workspace/ollama-models` - Ollama model storage
- `/workspace/logs` - System logs

## Development Workflow

Once the bootstrap is complete, you can:

1. Start tmux sessions for long-running processes
2. Activate the Python virtual environment:
   ```bash
   source /workspace/reverend/.venv/bin/activate
   ```

3. Launch OpenCode:
   ```bash
   opencode
   ```

## Notes

- The system will only install packages and tools on first run
- User changes to the repository are preserved automatically
- Ollama runs in background using tmux
- The default model is qwen3-coder:30b with 65K context length
- All secrets and credentials are handled through GitHub CLI
- SSH keys and tokens are never embedded in scripts or repositories  

## Troubleshooting

### Common Issues

1. **CUDA initialization fails** - This usually means the worker was provisioned without proper GPU support
2. **GitHub authentication needed** - Run `gh auth login` manually
3. **Network issues during model pull** - Can be skipped with `SKIP_MODEL_PULL=1`
4. **Ephemeral workspace detection** - Set `ALLOW_EPHEMERAL_WORKSPACE=1` to proceed

### Recovery

If bootstrap fails mid-process:
- Re-run the bootstrap script (idempotent)
- Check system logs in `/workspace/logs`
- Ensure network connectivity for package installations
- Verify GitHub token is valid if authentication is failing

## Architecture Compliance

This bootstrap ensures compliance with Reverend's design principles:

1. **Persistent intelligence, disposable compute** - Repository and model weights are stored persistently  
2. **Reproducible environments** - Same script produces same results on fresh pods
3. **Safety first** - CUDA validation before expensive operations
4. **Minimal dependencies** - Only installs what is required for development

## Development Lifecycle

1. **Start Pod** - Launch RunPod instance with persistent storage
2. **Bootstrap** - Run the script to create full environment 
3. **Develop** - Use OpenCode and Reverend tools for development
4. **Stop Pod** - Pod can be safely stopped without data loss (for persistent volumes)
5. **Resume** - Restart same Pod to resume work

## Security

The bootstrap maintains security by:
- Never exposing Ollama publicly 
- Keeping secrets in GitHub CLI managed tokens
- Preventing credential embedding in repository code
- Using tmux for safe process management
- Validating workspace persistence before proceeding

This environment is suitable for both local development and cloud-based AI-assisted engineering workflows.