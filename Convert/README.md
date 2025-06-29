##  Convert all pic and vid in a folder and save them into sub folders with json log to avoid re processing.

Defaults to a universal codec for social media and jpg.

Lowering quality from 100 to 95 reduces file size by a lot if you care about that, the quality loss is unnoticable by the human eye.

--p For only pic.

--v For only vid.

--one_to_one Instead of --nine_sixteen for aspect ratio.

--crop Crops the image instead of looking for a close resolution to match the aspect ratio.

python convert.py YanaSn0w1 ./downloads --output-dir ./downloads --debug --nine_sixteen
