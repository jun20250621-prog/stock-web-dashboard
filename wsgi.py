import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from main import app

if __name__ == "__main__":
    app.run()
