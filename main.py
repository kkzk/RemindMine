"""Main entry point for RemindMine AI Agent."""

import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from remindmine.app import main


if __name__ == "__main__":
    main()
