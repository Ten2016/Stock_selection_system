import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from app.utils.database import engine
from app.utils.data_migrations import repair_json_columns



def main():
    with engine.begin() as conn:
        repaired = repair_json_columns(conn)
    print(repaired)


if __name__ == '__main__':
    main()
