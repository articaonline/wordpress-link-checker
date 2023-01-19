import os
import requests
import csv
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import datetime
import time

while True:
    xml_file_input = input("Full path of the WordPress XML export file: ").strip("'")
    if xml_file_input.endswith(".xml") and os.path.isfile(xml_file_input):
        break
    else:
        print("Invalid path.")

with open(xml_file_input, "r") as xml_file, open("link-check.csv", "a") as csv_file:  # Open XML and CSV files
    csv_writer = csv.writer(csv_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)  # Create CSV writer object
    csv_writer.writerow(['Link', 'Status', 'Post title', 'Post link',
                         'Post date', 'Archived in IA', 'Recovered link', 'Date archived'])  # Write headings
    input_text = xml_file.read()
    tree = ET.fromstring(input_text)
    ns = {"content": "http://purl.org/rss/1.0/modules/content/"}  # This is for parsing XML with namespaces
    ns_2 = {"wp": "http://wordpress.org/export/1.2/"}
    list_post_titles = tree.findall("channel/item/title")
    list_post_links = tree.findall("channel/item/link")
    list_post_dates = tree.findall("channel/item/pubDate")
    list_post_content = tree.findall("channel/item/content:encoded", ns)
    list_content_links = []
    for content in list_post_content:
        soup = BeautifulSoup(content.text, "html.parser")
        single_content_links = soup.select('a[href]')
        list_content_links.append(list(single_content_links))

    total_link_count = 0
    ok_link_count = 0
    invalid_link_count = 0
    broken_link_count = 0
    already_ai_link_count = 0
    recovered_link_count = 0

    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/109.0"}

    for chunk in list_content_links:  # Loop through each link found in every post
        for link in chunk:
            total_link_count += 1
            link = link.get("href")
            print(str(total_link_count) + ". " + link, end=" ")
            post_title = list_post_titles[list_content_links.index(chunk)].text
            post_link = list_post_links[list_content_links.index(chunk)].text
            post_date = list_post_dates[list_content_links.index(chunk)].text
            if post_date is None:  # If post is not published, take draft date instead of published date.
                post_date = tree.findall("channel/item/wp:post_date", ns_2)[list_content_links.index(chunk)].text
                post_date = datetime.datetime.strptime(post_date, "%Y-%m-%d %H:%M:%S")
            else:
                post_date = datetime.datetime.strptime(post_date, "%a, %d %b %Y %H:%M:%S %z").replace(tzinfo=None)

            if link.startswith("http://web.archive.org") or link.startswith("https://web.archive.org"):  # Skip IA links
                already_ai_link_count += 1
                status = "Not checked"
                archived = ""
                recovered_link = ""
                date_archived = ""
            else:
                try:
                    resp = requests.head(link, headers=headers, timeout=15)  # Check each link
                    if resp.ok:
                        status = "OK"
                    else:
                        status = str(resp.status_code) + " error. " + resp.reason + "."
                except requests.exceptions.ConnectionError:
                    status = "Connection error"
                except requests.exceptions.MissingSchema:
                    status = "Internal or invalid link"
                except requests.exceptions.InvalidSchema:
                    status = "Invalid link"
                except:
                    status = "Unidentified error"

                if status in ["OK",
                              "Internal or invalid link",
                              "Invalid link"]:  # If link is OK or is invalid, don't look for it in IA
                    archived = ""
                    recovered_link = ""
                    date_archived = ""
                    if status == "OK":
                        ok_link_count += 1
                    elif status == "Internal or invalid link" or status == "Invalid link":
                        invalid_link_count += 1

                else:      # If the link is valid but broken, look for it in IA
                    broken_link_count += 1
                    while True:         # If IA doesn't respond, keep trying
                        try:
                            resp_ia = requests.get("http://web.archive.org/cdx/search/cdx?url="
                                                   + link).text  # AI provides a list of archived versions of the links
                            break
                        except requests.exceptions.ConnectionError:
                            print("Checking...", end=" ")
                            time.sleep(5)

                    if len(resp_ia) < 5:  # If the list of archived versions of the link is empty, skip
                        recovered_link = ""
                        archived = "No"
                        date_archived = ""
                    else:  # If there are archived links, find the closest to the date of publishing
                        list_archived_links = resp_ia.splitlines()
                        list_archived_dates = []
                        for row in list_archived_links:
                            date_str = row.split()[1]
                            date = datetime.datetime.strptime(date_str, "%Y%m%d%H%M%S")
                            list_archived_dates.append(date)

                        closest_date = min(list_archived_dates, key=lambda x: abs(x - post_date))

                        recovered_link_count += 1
                        recovered_link = "http://web.archive.org/web/" + closest_date.strftime("%Y%m%d%H%M%S") + "/" + link
                        archived = "Yes"
                        date_archived = str(closest_date)

            print(status)
            post_date = post_date.strftime("%Y-%m-%d %H:%M:%S")
            csv_writer.writerow([link, status, post_title, post_link, post_date, archived, recovered_link, date_archived])

    print("Finished. Found " + str(total_link_count) + " links.")
    print(str(ok_link_count) + " links OK.")
    print(str(invalid_link_count) + " links invalid.")
    print(str(broken_link_count) + " links broken.")
    print(str(recovered_link_count) + " links recovered with Internet Archive's Wayback Machine.")
    print(str(already_ai_link_count) + " links were already Wayback Machine snapshots.")

