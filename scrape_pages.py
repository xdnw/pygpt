import urllib

import json
import os
import re

import requests
from bs4 import BeautifulSoup

class PW_Wiki_Scrape:
    @staticmethod
    def getCategoryPages(categories):
        url = "https://politicsandwar.fandom.com/wiki/Category:" + categories

        while url:
            # div class="category-page__members"
            response = requests.get(url)
            soup = BeautifulSoup(response.content, "html.parser")

            pages = {}

            # get div
            div = soup.find("div", {"class": "category-page__members"})
            # get all links
            links = div.find_all("a")
            for link in links:
                # skip if href is empty or none
                if not link["href"]:
                    continue
                # skip if link text does not contain any letters
                if not any(c.isalpha() for c in link.text):
                    continue

                # skip if title contains Category:
                if "Category:" in link.text or "Category:" in link["href"]:
                    continue
                # add to pages
                pages[link.text] = link["href"]

            # Find the link to the next page
            nav_div = soup.find("div", {"class": "category-page__pagination"})
            if nav_div is not None:
                next_link = nav_div.find("a", {"class": "category-page__pagination-next"})
            else:
                next_link = None

            # If there is a next page, update the URL and continue
            if next_link is not None:
                url = next_link["href"]
            else:
                url = None

        return pages

    @staticmethod
    def getAllPages():
        # map of page name to page url
        pages = {}

        url = "https://politicsandwar.fandom.com/wiki/Special:AllPages"
        while url:
            response = requests.get(url)
            soup = BeautifulSoup(response.content, "html.parser")

            link_div = soup.find("ul", {"class": "mw-allpages-chunk"})

            # Find all the links within the div
            links = link_div.find_all("a")

            # Print the text of each link
            for link in links:

                # skip if href is empty or none
                if not link["href"]:
                    continue
                # skip if link text does not contain any letters
                if not any(c.isalpha() for c in link.text):
                    continue

                # print link text and url
                print(link.text, link["href"])
                # add to pages
                pages[link.text] = link["href"]


            # Find the link to the next page
            nav_div = soup.find("div", {"class": "mw-allpages-nav"})

            if nav_div is not None:
                next_link = nav_div.find("a", string=lambda s: s.startswith("Next page"))
            else:
                next_link = None

            # If there is a next page, update the URL and continue
            if next_link is not None:
                url = "https://politicsandwar.fandom.com" + next_link["href"]
            else:
                url = None

            print("Next: " + str(next_link))

            # If there is a next page, update the URL and continue
            if next_link:
                url = "https://politicsandwar.fandom.com" + next_link["href"]
            else:
                url = None
        return pages

    @staticmethod
    def getTable(blocks, page_element, title):
        # Find all the rows in the table
        rows = page_element.find_all('tr')

        # page title from url /
        key = title
        reset_key = False
        # Loop through each row and extract the key/value pairs

        for row in rows:
            # Get the cells in the row
            cells = row.find_all(['td', "th"])
            # If there are cells in the row, extract the key/value pairs

            if cells:
                # skip if cells length is less than 2
                if len(cells) == 1:
                    if reset_key:
                        reset_key = False
                        key = cells[0].get_text().strip()
                    # only if key is empty
                    continue
                if len(cells) < 2:
                    continue

                reset_key = True
                # The first cell is the key
                left = cells[0].get_text().strip()
                # The subsequent cells are the values
                right = [cell.get_text().strip() for cell in cells[1:]]
                combined = str((str(left), str(right)))

                # create list if not exist and append combined to blocks[key]
                blocks.setdefault(key, []).append(combined)

    @staticmethod
    def extractSections(url):
        response = requests.get(url)
        page_title = url.split("/")[-1]
        print("Extracting: " + url)

        soup = BeautifulSoup(response.content, "html.parser")

        blocks = {}

        # get mw-parser-output div
        div = soup.find("div", {"class": "mw-parser-output"})
        # get second child
        # if length is sufficient
        if len(div.contents) > 2:
            child = div.contents[2]
            # if first child is table
            if child and child.name == "table":
                PW_Wiki_Scrape.getTable(blocks, child, page_title)

        # get the content before the first h2 inside mw-parser-output
        content = ""
        for element in div.contents:
            if element.name == "table":
                continue
            if element.name == "h2" or element.name == "h3" or element.name == "div":
                break
            content += str(element.text.strip())

        # trim content
        blocks[page_title] = content.strip()

        for heading in soup.find_all(["h2", "h3"]):  # find separators, in this case h2 and h3 nodes
            if heading.text == "Related links":
                break
            values = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ["h2", "h3"]:  # iterate through siblings until separator is encountered
                    break
                text = sibling.text.strip()
                if text == "":
                    continue
                values.append(text)
            if heading.name == "h2":
                # if values is not, or is empty list or is empty string continue
                if not values or values == "" or values == []:
                    continue
                blocks[heading.text] = values
            elif heading.name == "h3":
                h2_heading = heading.find_previous_sibling("h2")
                if h2_heading is not None:
                    h2_text = h2_heading.text
                    h3_text = heading.text

                    # skip if values is empty
                    if not values or values == "" or values == []:
                        continue

                    blocks[f"{h2_text}.{h3_text}"] = values

        return blocks

    @staticmethod
    def saveToJson(url):
        blocks = PW_Wiki_Scrape.extractSections(url)
        page_name = url.split("/")[-1]
        # strip non filename chars
        page_name = re.sub(r'[^\w\s]', '', page_name)
        # replace spaces with _
        page_name = page_name.replace(" ", "_")

        # test
        if not os.path.exists("json"):
            os.makedirs("json")

        # save to json
        with open(f"json/{page_name}.json", "w+") as outfile:
            json.dump(blocks, outfile, indent=4)

    @staticmethod
    def fetchDefaultPages():
        pages_to_save = set()
        pages_to_save.add("Frequently_Asked_Questions")
        pages_to_save.add("Paperless")

        categories_to_save = ["Wars", "Alliances", "Treaties", "Guides", "Mechanics", "API"]
        # iterate categories
        for category in categories_to_save:
            # get the pages from each category
            pages = PW_Wiki_Scrape.getCategoryPages(category)
            # iterate pages--
            for page in pages:
                # get page name
                page_name = page.split("/")[-1]
                # save to json
                pages_to_save.add(page_name)
        # save to sitemap.json
        with open("sitemap.json", "w+") as outfile:
            json.dump(list(pages_to_save), outfile, indent=4)

    @staticmethod
    def getSitemapCached():
        # if file not exists, fetch and save to sitemap.json
        filename = "sitemap.json"
        if not os.path.exists(filename):
            print("Fetching default pages")
            PW_Wiki_Scrape.fetchDefaultPages()

        with open("sitemap.json", "r") as infile:
            print("Loading sitemap.json")
            return json.load(infile)


    @staticmethod
    def saveDefaultPages():
        skipSet = set()
        skipSet.add("doc")
        skipSet.add("Python")

        _pages_to_save = PW_Wiki_Scrape.getSitemapCached()

        # iterate each page
        for page in _pages_to_save:
            if (page in skipSet):
                continue
            url = f"https://politicsandwar.fandom.com/wiki/{urllib.parse.quote(page)}"

            # strip non filename chars
            page_name = re.sub(r'[^\w\s]', '', page)
            # replace spaces with _
            page_name = page_name.replace(" ", "_")

            # check if file exists
            if os.path.exists(f"json/{page_name}.json"):
                print(f"Skipping {page_name}.json")
                continue

            # save to json
            print(f"Saving {page_name}.json")
            PW_Wiki_Scrape.saveToJson(url)

PW_Wiki_Scrape.saveDefaultPages()