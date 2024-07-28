import sys
print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")

import torch

def test_torch():
    print(f"Torch version: {torch.__version__}")
    x = torch.rand(5, 3)
    print(x)

if __name__ == "__main__":
    test_torch()
