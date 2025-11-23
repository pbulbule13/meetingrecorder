#!/bin/bash

# Nexus Assistant - Automated Setup Script
# This script installs all dependencies and prepares the environment

set -e  # Exit on error

echo "========================================="
echo "   Nexus Assistant - Setup Script"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if command exists
command_exists() {
  command -v "$1" >/dev/null 2>&1
}

# Print colored message
print_success() {
  echo -e "${GREEN}✓${NC} $1"
}

print_error() {
  echo -e "${RED}✗${NC} $1"
}

print_info() {
  echo -e "${YELLOW}➜${NC} $1"
}

# Step 1: Check prerequisites
echo "Step 1: Checking prerequisites..."
echo "-----------------------------------"

# Check Node.js
if command_exists node; then
  NODE_VERSION=$(node -v)
  print_success "Node.js is installed: $NODE_VERSION"

  # Check if version is >= 20
  NODE_MAJOR=$(echo $NODE_VERSION | cut -d'.' -f1 | sed 's/v//')
  if [ "$NODE_MAJOR" -lt 20 ]; then
    print_error "Node.js version 20 or higher is required"
    exit 1
  fi
else
  print_error "Node.js is not installed"
  print_info "Please install Node.js 20+ from https://nodejs.org/"
  exit 1
fi

# Check Python
if command_exists python3; then
  PYTHON_VERSION=$(python3 --version)
  print_success "Python is installed: $PYTHON_VERSION"

  # Check if version is >= 3.11
  PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')
  if [ "$PYTHON_MINOR" -lt 11 ]; then
    print_error "Python 3.11 or higher is required"
    exit 1
  fi
else
  print_error "Python 3 is not installed"
  print_info "Please install Python 3.11+ from https://www.python.org/"
  exit 1
fi

# Check FFmpeg
if command_exists ffmpeg; then
  FFMPEG_VERSION=$(ffmpeg -version | head -n 1)
  print_success "FFmpeg is installed: $FFMPEG_VERSION"
else
  print_error "FFmpeg is not installed"
  print_info "Installing FFmpeg..."

  # Try to install based on OS
  if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    if command_exists brew; then
      brew install ffmpeg
      print_success "FFmpeg installed via Homebrew"
    else
      print_error "Homebrew not found. Please install FFmpeg manually"
      exit 1
    fi
  elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    if command_exists apt-get; then
      sudo apt-get update
      sudo apt-get install -y ffmpeg
      print_success "FFmpeg installed via apt"
    elif command_exists yum; then
      sudo yum install -y ffmpeg
      print_success "FFmpeg installed via yum"
    else
      print_error "Package manager not found. Please install FFmpeg manually"
      exit 1
    fi
  else
    print_error "Please install FFmpeg manually from https://ffmpeg.org/"
    exit 1
  fi
fi

echo ""

# Step 2: Install Node.js dependencies
echo "Step 2: Installing Node.js dependencies..."
echo "-------------------------------------------"

npm install

print_success "Node.js dependencies installed"
echo ""

# Step 3: Install Python dependencies
echo "Step 3: Installing Python dependencies..."
echo "-----------------------------------------"

# Create virtual environment (optional but recommended)
if [ ! -d "venv" ]; then
  print_info "Creating Python virtual environment..."
  python3 -m venv venv
fi

# Activate virtual environment
print_info "Activating virtual environment..."
source venv/bin/activate || . venv/Scripts/activate

# Upgrade pip
print_info "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
print_info "Installing Python packages..."
pip install -r requirements.txt

print_success "Python dependencies installed"
echo ""

# Step 4: Setup environment file
echo "Step 4: Configuring environment..."
echo "-----------------------------------"

if [ ! -f ".env" ]; then
  print_info "Creating .env file from template..."
  cp .env.example .env
  print_success ".env file created"

  print_info "⚠️  IMPORTANT: Edit .env file and add your API keys:"
  echo "   - DEEPGRAM_API_KEY or ASSEMBLYAI_API_KEY or OPENAI_API_KEY (for STT)"
  echo "   - GEMINI_API_KEY or OPENAI_API_KEY or ANTHROPIC_API_KEY (for LLM)"
  echo ""
else
  print_info ".env file already exists (not overwriting)"
fi

echo ""

# Step 5: Create necessary directories
echo "Step 5: Creating data directories..."
echo "-------------------------------------"

mkdir -p data/meetings
mkdir -p data/transcripts
mkdir -p data/audio
mkdir -p logs

print_success "Data directories created"
echo ""

# Step 6: Run tests (optional)
echo "Step 6: Running tests (optional)..."
echo "------------------------------------"

read -p "Do you want to run tests now? (y/N) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
  print_info "Running tests..."
  npm test
  print_success "Tests completed"
else
  print_info "Skipping tests"
fi

echo ""

# Setup complete
echo "========================================="
echo "   Setup Complete! 🎉"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Edit .env file and add your API keys"
echo "2. Run 'npm run dev' to start the application"
echo "3. Check DOCUMENTATION.html for full documentation"
echo ""
echo "Useful commands:"
echo "  npm run dev          - Start in development mode"
echo "  npm test             - Run tests"
echo "  npm run build:win    - Build for Windows"
echo "  npm run build:mac    - Build for macOS"
echo "  npm run build:linux  - Build for Linux"
echo ""
print_success "Happy meeting recording!"
