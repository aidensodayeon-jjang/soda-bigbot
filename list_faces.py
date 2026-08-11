import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import face_db


def main():
    names, _ = face_db.load_all()

    print("등록된 얼굴 ({}명):".format(len(names)))
    for name in names:
        print(" -", name)


if __name__ == "__main__":
    main()
