#!/bin/bash
set -e

# This script builds the sonata webpage

# first find all arxiv papers that correspond to members of sonata
cd scripts
python3 scrape_arxiv.py
cd ../

# now insert the result of that scraping into the home page
cd html
cp templates/*.html .
sed -i -e "/<!--INSERTHERE-->/r arxiv-scrape-results.html" index.html
see index.html
