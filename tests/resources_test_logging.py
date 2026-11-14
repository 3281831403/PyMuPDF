
import sys
sys.stdout = None
import pymupdf

pymupdf.message('this is pymupdf.message()')
pymupdf.log('this is pymupdf.log()')
