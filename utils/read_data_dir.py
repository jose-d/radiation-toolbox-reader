#!/usr/bin/env python3

import sys
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

def init_logging():
    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s',
                        level=logging.INFO)
    
def main(data_dir, data_format):
    init_logging()

    from reader.exceptions import ReaderError

    if not Path(data_dir).is_dir():
        logging.critical(f"Directory {data_dir} doesn't exist")
        return 1

    if data_format == "log":
        ext = "*.[lL][oO][gG]"
        from reader.safecast import SafecastReader as Reader
    else:
        ext = "*.[eE][rR][sS]"
        from reader.ers import ERSReader as Reader

    files = sorted(Path(data_dir).rglob(ext))
    if len(files) < 1:
        logging.critical(f"No {data_format.upper()} files found in directory {data_dir}")

    files_count = len(files)
    i = 1
    for fn in files:
        logging.info(f"Reading {fn.name} ({i} of {files_count})...")
        try:
            with Reader(fn) as r:
                logging.info(f"Success - {r.count()} records")
        except ReaderError as e:
            logging.error(e)

        i += 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='read_data_dir',
        description='Read all files from data directory.')
    parser.add_argument('--data_dir',
                        type=str, required=True,
                        help='Data directory.')
    parser.add_argument('--data_format',
                        type=str, choices=('log', 'ers'),
                        default='ers', help='Expected data format (file extension).')
    
    args = parser.parse_args()

    sys.exit(main(args.data_dir, args.data_format))
    
