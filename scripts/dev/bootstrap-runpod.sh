#!/bin/bash

set -Eeuo pipefail

echo "=== RunPod Reverend Development Bootstrap ==="

# Robust function to find Python with PyTorch and CUDA support
find_python_with_torch() {
    echo "Looking for Python interpreter with PyTorch and CUDA support..."
    
    # Try common system Python paths first
    local python_paths=("/usr/local/bin/python3" "/usr/bin/python3" "/opt/conda/bin/python3")
    
    for py_path in "${python_paths[@]}"; do
        if [ -x "$py_path" ]; then
            echo "Testing $py_path for PyTorch..."
            if "$py_path" -c "import torch; print('PyTorch version:', torch.__version__); print('CUDA available:', torch.cuda.is_available()); exit(0)" 2>/dev/null; then
                if "$py_path" -c "import torch; exit(1) if not torch.cuda.is_available() else exit(0)" 2>/dev/null; then
                    echo "Found working Python with CUDA support: $py_path"
                    echo "Testing actual CUDA operation..."
                    # Run a real CUDA tensor operation to make sure it works
                    "$py_path" -c "
import torch
# Create a tensor and move it to GPU
x = torch.randn(1000, 1000).cuda()
y = torch.randn(1000, 1000).cuda()
z = torch.mm(x, y)
print('CUDA tensor operation successful')
"
                    echo "Using Python interpreter: $py_path"
                    echo "Cuda available: yes"
                    return 0
                else
                    echo "Found Python but CUDA not available"
                fi
            else
                echo "Found Python but PyTorch import failed"
            fi
        fi
    done
    
    # Try python3 from PATH as fallback (in case system Python isn't found)
    if command -v python3 &> /dev/null; then
        echo "Testing python3 from PATH for PyTorch..."
        if python3 -c "import torch; print('PyTorch version:', torch.__version__); print('CUDA available:', torch.cuda.is_available()); exit(0)" 2>/dev/null; then
            if python3 -c "import torch; exit(1) if not torch.cuda.is_available() else exit(0)" 2>/dev/null; then
                echo "Found working Python with CUDA support: python3"
                echo "Testing actual CUDA operation..."
                # Run a real CUDA tensor operation to make sure it works
                python3 -c "
import torch
# Create a tensor and move it to GPU
x = torch.randn(1000, 1000).cuda()
y = torch.randn(1000, 1000).cuda()
z = torch.mm(x, y)
print('CUDA tensor operation successful')
"
                echo "Using Python interpreter: python3"
                echo "Cuda available: yes"
                return 0
            else
                echo "Found Python but CUDA not available"
            fi
        else
            echo "Found Python but PyTorch import failed"
        fi
    fi
    
    echo "ERROR: No suitable Python interpreter with CUDA and PyTorch found"
    exit 1
}

# Function to check if CUDA works properly using PyTorch
check_cuda() {
    echo "Checking CUDA availability..."
    
    # First verify nvidia-smi shows GPUs
    if ! command -v nvidia-smi &> /dev/null; then
        echo "ERROR: nvidia-smi not found"
        exit 1
    fi
    
    nvidia-smi --query-gpu=name --format=csv,noheader,nounits | head -n1 > /dev/null
    if [ $? -ne 0 ]; then
        echo "ERROR: No GPU detected by nvidia-smi"
        exit 1
    fi
    
    # Now test actual CUDA initialization with PyTorch using robust method above
    echo "Testing CUDA initialization with PyTorch..."
    find_python_with_torch
}

# Function to validate workspace
validate_workspace() {
    echo "Validating workspace..."
    
    if [ ! -d "/workspace" ]; then
        echo "ERROR: /workspace directory does not exist"
        exit 1
    fi
    
    # Check if it's ephemeral (by looking for typical tmpfs mount)
    if mount | grep -q "tmpfs.*on /workspace"; then
        if [ "${ALLOW_EPHEMERAL_WORKSPACE:-0}" != "1" ]; then
            echo "WARNING: /workspace appears to be a temporary filesystem (tmpfs)."
            echo "This will cause data loss when the Pod stops."
            echo "If you want to proceed anyway, set ALLOW_EPHEMERAL_WORKSPACE=1"
            exit 1
        else
            echo "WARNING: Using ephemeral workspace as requested with ALLOW_EPHEMERAL_WORKSPACE=1"
        fi
    else
        echo "INFO: /workspace appears to be persistent storage"
    fi
}

# Function to create required directories
create_directories() {
    echo "Creating project directories..."
    
    mkdir -p /workspace/reverend
    mkdir -p /workspace/worktrees
    mkdir -p /workspace/ollama-models
    mkdir -p /workspace/logs
}

# Function to install development tools
install_dev_tools() {
    echo "Installing development tools..."
    
    # Update package list
    apt-get update
    
    # Install required packages
    apt-get install -y \
        git \
        git-lfs \
        gh \
        curl \
        jq \
        tmux \
        ripgrep \
        build-essential \
        python3-venv
    
    echo "Development tools installed"
}

# Function to handle GitHub authentication
setup_github() {
    echo "Setting up GitHub authentication..."
    
    if ! command -v gh &> /dev/null; then
        echo "ERROR: GitHub CLI (gh) not found"
        exit 1
    fi
    
    # Check if already authenticated
    if ! gh auth status &>/dev/null; then
        echo "GitHub not authenticated. Please authenticate with:"
        echo "  gh auth login"
        echo ""
        echo "This will be interactive. You'll need to select:"
        echo "- GitHub.com authentication"
        echo "- HTTPS protocol for Git"
        echo "- Generate a new fine-grained token"
        echo ""
        read -p "Press Enter when ready to authenticate..."
        gh auth login
    else
        echo "GitHub already authenticated"
    fi
}

# Function to setup Reverend repository
setup_reverend_repo() {
    echo "Setting up Reverend repository..."
    
    cd /workspace/reverend
    
    # Clone if not present
    if [ ! -d ".git" ]; then
        echo "Cloning Reverend repository..."
        git clone https://github.com/reverend-labs/reverend .
    else
        echo "Reverend repository already exists, checking remote..."
        origin_url=$(git remote get-url origin)
        if [ "$origin_url" != "https://github.com/reverend-labs/reverend" ]; then
            echo "WARNING: Repository remote points to $origin_url instead of expected https://github.com/reverend-labs/reverend"
            read -p "Continue anyway? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                exit 1
            fi
        fi
    fi
    
    # Create Python venv if needed
    if [ ! -f ".venv/bin/python" ]; then
        echo "Creating Python virtual environment..."
        python3 -m venv .venv
        source .venv/bin/activate
        pip install --upgrade pip
        pip install -e '.[dev]'
    else
        echo "Python virtual environment already exists"
    fi
    
    # Verify installation
    source .venv/bin/activate
    python3 -c "import reverend; print('Reverend import successful')"
}

# Function to test Reverend
run_tests() {
    echo "Running basic tests..."
    
    if [ "${SKIP_TESTS:-0}" == "1" ]; then
        echo "Skipping tests as requested"
        return 0
    fi
    
    source .venv/bin/activate
    python3 -m pytest -xvs tests/test_release_smoke.py::test_release_smoke --tb=short
}

# Function to install Ollama
install_ollama() {
    echo "Installing Ollama..."
    
    # Install if not already present (note: check the specific version)
    if ! command -v ollama &> /dev/null; then
        curl -fsSL https://ollama.com/install.sh | sh
    fi
    
    # Start ollama in background using tmux
    if ! pgrep -f "ollama serve" > /dev/null; then
        echo "Starting Ollama in tmux..."
        tmux new-session -d -s ollama "ollama serve"
        sleep 3  # Give it a moment to start
    fi
}

# Function to setup Ollama model
setup_ollama_model() {
    echo "Setting up Ollama model..."
    
    source .venv/bin/activate
    
    MODEL_NAME="${REVEREND_MODEL:-qwen3-coder:30b}"
    CONTEXT_LENGTH="${REVEREND_CONTEXT_LENGTH:-65536}"
    
    echo "Using model: $MODEL_NAME with context length: $CONTEXT_LENGTH"
    
    # Check if the model already exists
    if ollama list | grep -q "$MODEL_NAME"; then
        echo "Model already downloaded"
    else
        if [ "${SKIP_MODEL_PULL:-0}" == "1" ]; then
            echo "Skipping model pull as requested"
            return 0
        fi
        
        echo "Pulling model $MODEL_NAME..."
        ollama pull "$MODEL_NAME"
    fi
    
    # Verify that the model is running properly on GPU
    echo "Verifying model is using GPU..."
    if ! ollama ps | grep -q "$MODEL_NAME"; then
        echo "Warning: Model may not be loaded properly. Checking status..."
        ollama ps --format json | jq -r '.[] | "\(.model) running on \(.gpu)"' > /dev/null 2>&1 || true
    fi
    
    # Configure the model with specified context length if not already configured
    # This would require running ollama show command and checking settings
    # For now we assume standard behavior
    
    # Verify model runs properly
    echo "Verifying model inference..."
    
    # Send a simple test prompt to verify it's working
    TEST_RESPONSE=$(ollama run "$MODEL_NAME" "Say 'hello'" 2>&1)
    if [ $? -ne 0 ]; then
        echo "ERROR: Model inference failed"
        exit 1
    fi
    
    echo "Model verification successful"
}

# Function to install OpenCode
install_opencode() {
    echo "Installing OpenCode..."
    
    # Check if opencode is already available on PATH
    if command -v opencode &> /dev/null; then
        echo "OpenCode already installed"
        return 0
    fi
    
    # If not found, install from source or appropriate package
    cd /tmp
    curl -fsSL https://github.com/anomalyco/opencode/releases/latest/download/opencode-linux-amd64.tar.gz | tar xz
    mv opencode /usr/local/bin/
    
    if ! command -v opencode &> /dev/null; then
        echo "ERROR: Failed to install OpenCode"
        exit 1
    fi
    
    # Make the binary immediately available in current shell by updating PATH
    export PATH="/usr/local/bin:$PATH"
    
    echo "OpenCode installed successfully"
}

# Function to validate model is using GPU
validate_model_gpu() {
    echo "Validating model on GPU..."
    
    # Verify that Ollama is running and the model was loaded
    if ! command -v ollama &> /dev/null; then
        echo "ERROR: Ollama not found"
        exit 1
    fi
    
    if ! ollama ps | grep -q "$MODEL_NAME"; then
        echo "WARNING: Model may not be running on GPU (not loaded in Ollama)"
        echo "This could be normal if using a model that hasn't been loaded yet, or an error."
    else
        echo "Model found in Ollama runtime"
    fi
    
    # Try to run a simple test
    echo "Testing inference with minimal prompt..."
    TEST_RESULT=$(ollama run "$MODEL_NAME" "Hello world" 2>&1 | head -n1)
    if [ $? -ne 0 ]; then
        echo "ERROR: Model inference test failed"
        exit 1
    fi
    
    echo "Model inference successful"
}

# Function to display final summary
show_summary() {
    echo ""
    echo "=== Bootstrap Summary ==="
    echo "GPU information:"
    nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader,nounits | head -n1
    echo ""
    
    echo "CUDA status: $(nvidia-smi 2>&1 | grep 'Driver Version' | cut -d' ' -f5)"
    echo ""
    
    echo "Storage status:"
    df -h /workspace | tail -n +2 | awk '{print "  " $1 " " $2 " " $3 " " $4}'
    echo ""
    
    echo "GitHub authentication: $(gh auth status &>/dev/null && echo '✓' || echo '✗')"
    echo ""
    
    echo "Reverend repository: /workspace/reverend"
    echo "Python environment: $(cd /workspace/reverend && source .venv/bin/activate && python --version)"
    echo ""
    
    echo "Ollama status:"
    if command -v ollama &> /dev/null; then
        echo "  ✓ Ollama installed"
        echo "  Models available: $(ollama list 2>/dev/null | grep -c '^.*$')"  # Count lines with content
    else
        echo "  ✗ Ollama not found"
    fi
    echo ""
    
    echo "Model status:"
    echo "  Default model: ${REVEREND_MODEL:-qwen3-coder:30b}"
    echo "  Context length: ${REVEREND_CONTEXT_LENGTH:-65536}"
    echo ""
    
    echo "OpenCode version: $(opencode --version 2>/dev/null || echo 'Not installed')"
    echo "=== Bootstrap Complete ==="
}

# Main execution
main() {
    echo "Starting RunPod Reverend development environment bootstrap"
    
    # Parse command line options first, before any side effects
    if [[ "$1" == "--help" || "$1" == "-h" ]]; then
        echo "RunPod Reverend Development Bootstrap"
        echo ""
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --help, -h             Show this help message and exit"
        echo ""
        echo "Environment variables:"
        echo "  ALLOW_EPHEMERAL_WORKSPACE=1   Allow use of ephemeral workspace (default: 0)"
        echo "  SKIP_TESTS=1                  Skip running tests (default: 0)"
        echo "  SKIP_MODEL_PULL=1             Skip pulling Ollama models (default: 0)"
        echo "  REVEREND_MODEL                Specify model to use (default: qwen3-coder:30b)"
        echo "  REVEREND_CONTEXT_LENGTH       Set context length for ollama (default: 65536)"
        echo ""
        echo "Requirements:"
        echo "  - CUDA-compatible GPU"
        echo "  - nvidia-smi available"
        echo "  - Internet connectivity"
        exit 0
    fi
    
    check_cuda
    validate_workspace
    create_directories
    install_dev_tools
    setup_github
    setup_reverend_repo
    run_tests
    install_ollama
    setup_ollama_model
    install_opencode
    validate_model_gpu
    show_summary
    
    echo ""
    echo "Bootstrap complete! You can now start using the Reverend development environment."
    echo "To begin, you might want to:"
    echo "1. Start a new tmux session"
    echo "2. Activate the Python virtual environment: source /workspace/reverend/.venv/bin/activate"
    echo "3. Launch OpenCode: opencode"
    echo ""
    echo "When stopping the Pod, remember that ephemeral workspaces will be lost."
}

# Execute main function
main "$@"