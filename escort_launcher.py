"""Preview executable entry; command-line --mode can still select classic."""
import sys
from game3d import Game3D, options


if __name__ == "__main__":
    application = Game3D(options(["--mode", "escort", *sys.argv[1:]]))
    try:
        application.run()
    finally:
        application.destroy()
