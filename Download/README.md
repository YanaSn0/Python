## download.py

## Download with custom name.

python download.py YanaSn0w1 full --debug --output-dir ./output

## With title as name.

python download.py full --debug --output-dir ./output

## Download Audio Only

## Saves audio as .m4a files.

python download.py audio --debug

## Download Video Only

## Saves video without audio as .mp4 files.

python download.py video --output-dir ./videos --debug 

## Download and Split into Video and Audio

## Saves separate video (.mp4) and audio (.m4a) files.

python download.py split --output-dir ./split --debug   

## Download with Duration Limit

## Limits downloaded media duration (e.g., first 30 seconds).

python download.py combined --output-dir ./combined --duration 30 --debug  

## Download with URL-Based Naming

## Names audio files based on URL instead of title.

python download.py audio --output-dir ./audio --link --debug  

## Keep Original Files

## Preserves original files without re-encoding.

python download.py combined --output-dir ./combined --keep-original --debug  

## Clear Output Directory

## Clears the output directory before downloading.

python download.py audio --output-dir ./audio --clear-dir --debug
