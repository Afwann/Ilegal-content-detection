import subprocess
import os
import shutil
import time
from dotenv import load_dotenv
import scrapy
from scrapy.crawler import CrawlerProcess
import logging
from urllib.parse import urlsplit, urlunsplit
import re
import scrapy


class SubdomainSpider(scrapy.Spider):
    name = 'subdomain_spider'

    def __init__(self, subdomains):
        self.start_urls = [self.normalize_url(f"https://{subdomain.strip()}") for subdomain in subdomains]
        self.allowed_domains = [subdomain.strip() for subdomain in subdomains]
        self.visited_urls = set()  
        self.keywords = ['judi','gacor','togel','toto','4d','bandar','mix parlay','sbobet','onlyfans','pragmatic','bonanza','zeus','slot']
        logging.info(f"Start URLs: {self.start_urls}")
        logging.info(f"Allowed Domains: {self.allowed_domains}")

    def normalize_url(self, url):
        parsed_url = urlsplit(url)
        normalized_path = parsed_url.path.rstrip('/') or '/'
        normalized_url = urlunsplit((parsed_url.scheme, parsed_url.netloc, normalized_path, parsed_url.query, parsed_url.fragment))
        if normalized_url.startswith("http://http://") or normalized_url.startswith("https://https://"):
            normalized_url = normalized_url.replace("http://http://", "http://").replace("https://https://", "https://")
        return normalized_url

    def handle_https_fallback(self, response):
        if response.status in (403, 530):
            http_url = response.url.replace("https://", "http://")
            normalized_http_url = self.normalize_url(http_url)
            if normalized_http_url not in self.visited_urls:
                logging.warning(f"HTTPS failed, trying HTTP: {http_url}")
                return scrapy.Request(http_url, callback=self.parse)
        return None

    def parse(self, response):
        normalized_url = self.normalize_url(response.url)
        http_fallback_request = self.handle_https_fallback(response)
        if http_fallback_request:
            yield http_fallback_request
            return
        
        if normalized_url in self.visited_urls:
            logging.info(f"Skipping already visited URL: {normalized_url}")
            return
        
        self.visited_urls.add(normalized_url)
        logging.info(f"Visiting: {normalized_url}")

        page_content = response.text.lower()

        
        keywords_found = [keyword for keyword in self.keywords if re.search(r'(?<!\w)' + re.escape(keyword) + r'(?!\w)', page_content)]
        
        if keywords_found:
            page_title = response.css('title::text').get(default='No title found')
            yield {
                'url': normalized_url,
                'title': page_title,
                'keywords_found': keywords_found
            }

        links = response.css('a::attr(href)').getall()
        for link in links:
            absolute_url = response.urljoin(link)
            normalized_link = self.normalize_url(absolute_url)
            if self.is_valid_url(normalized_link):
                if normalized_link not in self.visited_urls:
                    logging.info(f"Following link: {normalized_link}")
                    yield response.follow(normalized_link, callback=self.parse)

    def is_valid_url(self, url):
        if url.startswith("mailto:") or url.startswith("javascript:") or url.startswith("tel:"):
            return False
        return url.startswith("http")


class SubdomainScanner:
    def __init__(self, domain, output_file, directory):
        self.domain = domain
        self.output_file = output_file
        self.directory = directory
        self.time_log_file = os.path.join(directory, "time.txt") 

    def log_time(self, function_name, start_time, end_time):
        start_readable = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))
        end_readable = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(end_time))
        duration = end_time - start_time
        with open(self.time_log_file, 'a') as log_file:
            log_file.write(f"{function_name} - START: {start_readable} END: {end_readable} HOW LONG: {duration:.2f} seconds\n")

    # Amass Subdomain Enumeration
    def enum_subdomain(self):
        start_time = time.time()
        try:
            print(f"Starting Amass scan for domain: {self.domain}")
            
            command = f"amass enum -d {self.domain}  -p 80,443 -active -brute -oA {self.output_file} -dir {self.directory} "
            subprocess.run(command, shell=True, check=True)

            print(f"Amass scan completed for domain: {self.domain}")
        except subprocess.CalledProcessError as e:
            print(f"An error occurred during the Amass scan: {str(e)}")
        finally:
            end_time = time.time() 
            self.log_time("Amass Scan", start_time, end_time)

    # Change folder location
    def check_output(self):
        base_name = os.path.splitext(self.output_file)[0]
        output_files = [f"{base_name}.txt", f"{base_name}.json"]

        for file_name in output_files:
            if os.path.exists(file_name):
                with open(file_name, 'r') as file:
                    content = file.read()

                if content:
                    print(f"\nSubdomains have been saved to {file_name}")

                    new_directory = self.directory
                    os.makedirs(new_directory, exist_ok=True)
                    new_file_path = os.path.join(new_directory, os.path.basename(file_name))

                    shutil.move(file_name, new_file_path)
                    print(f"File moved to {new_file_path}")
                else:
                    print(f"The file {file_name} exists but is empty.")
            else:
                print(f"Failed to save subdomains to {file_name}")


 
    def start_spider(self, file_path):
        """Memulai proses crawling berdasarkan daftar subdomain dari file."""
        start_time = time.time()

        
        with open(file_path, 'r') as file:
            subdomains = file.readlines()

        
        output_json = os.path.join(self.directory, f"output_{os.path.basename(self.output_file)}.json")

        
        process = CrawlerProcess(settings={
            'FEEDS': {
                output_json: {'format': 'json'},
            },
            'LOG_LEVEL': 'INFO',
            # 'CONCURRENT_REQUESTS': 16,
            # 'DOWNLOAD_DELAY': 1,
            'RETRY_TIMES': 5,
            'USER_AGENT': 'Mozilla/5.0 (compatible; ScrapyBot/1.0; +http://example.com)',
            'DUPEFILTER_DEBUG': True,
            'RANDOM_UA_PER_PROXY': True,
            'USER_AGENTS': [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
                'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:54.0) Gecko/20100101 Firefox/54.0',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/44.0.2403.157 Safari/537.36',
            ]
        })

        logging.info(f"Starting Scrapy Spider for {len(subdomains)} subdomains")
        process.crawl(SubdomainSpider, subdomains=subdomains)
        process.start()

        
        end_time = time.time()
        self.log_time("Scrapy Spider", start_time, end_time)

# Usage
if __name__ == "__main__":
    load_dotenv()

    domain = os.getenv("DOMAIN") 
    output_file = os.getenv("OUTPUT_FILE")
    directory = os.getenv("DIRECTORY")
    
    scanner = SubdomainScanner(domain, output_file, directory)
    # # scanner.enum_subdomain()
    # # scanner.check_output()
    # scanner.start_spider(f'{directory}{output_file}.txt')



    dns_auto = input("Do you want to Automate DNS Enum ? [Y/n]")

    if dns_auto == 'Y' :
        domain = input("Enter the domain you want to search :")
        scanner.enum_subdomain(domain)
        scanner.check_output()
        SubdomainScanner
    else:
        subdomains_file = input("Enter the path to the .txt file with the list of subdomains: ")

        file_name_without_ext = os.path.splitext(os.path.basename(subdomains_file))[0]

        new_directory = os.path.join("subdomain_output", file_name_without_ext)
        os.makedirs(new_directory, exist_ok=True)

        new_file_path = os.path.join(new_directory, os.path.basename(subdomains_file))
    
        shutil.copy(subdomains_file, new_file_path)
        print(f"File moved to {new_file_path}")

        scanner.start_spider(new_file_path)
