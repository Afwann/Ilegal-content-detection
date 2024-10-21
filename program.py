import subprocess
import os
import shutil
import scrapy
from scrapy.crawler import CrawlerProcess
import logging
from urllib.parse import urlsplit, urlunsplit
from elasticsearch import Elasticsearch, helpers
from dotenv import load_dotenv


load_dotenv()

class SubdomainSpider(scrapy.Spider):
    name = 'subdomain_spider'

    def __init__(self, subdomains, es_client, es_index):
        self.start_urls = [self.normalize_url(f"https://{subdomain.strip()}") for subdomain in subdomains]
        self.allowed_domains = [subdomain.strip() for subdomain in subdomains]
        self.visited_urls = set()
        self.es_client = es_client 
        self.es_index = es_index 
        logging.info(f"Start URLs: {self.start_urls}")
        logging.info(f"Allowed Domains: {self.allowed_domains}")

    def normalize_url(self, url):
        parsed_url = urlsplit(url)
        normalized_path = parsed_url.path.rstrip('/') or '/'
        return urlunsplit((parsed_url.scheme, parsed_url.netloc, normalized_path, parsed_url.query, parsed_url.fragment))

    def handle_https_fallback(self, response):
        if response.status in (403, 530):
            http_url = response.url.replace("https://", "http://")
            normalized_http_url = self.normalize_url(http_url)
            if normalized_http_url not in self.visited_urls:
                logging.warning(f"HTTPS failed, trying HTTP: {http_url}")
                return scrapy.Request(http_url, callback=self.parse)
        return None
    
    def is_malformed_url(self, url):
        parsed_url = urlsplit(url)
        if '/http/' in parsed_url.path or '/https/' in parsed_url.path:
            logging.warning(f"Malformed URL detected with '/http/' or '/https/': {url}")
            return True
        return False

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
        page_title = response.css('title::text').get(default='No title found')

        internal_links = set()
        external_links = set()


        links = response.css('a::attr(href)').getall()
        for link in links:
            absolute_url = response.urljoin(link)
            normalized_link = self.normalize_url(absolute_url)

            if self.is_malformed_url(normalized_link):
                logging.warning(f"Skipping malformed internal/external URL: {normalized_link}")
                continue



            if self.is_valid_url(normalized_link) and normalized_link not in self.visited_urls:
                if self.is_internal_link(normalized_link):
                    internal_links.add(normalized_link)
                    logging.info(f"Following internal link: {normalized_link}")
                    yield response.follow(normalized_link, callback=self.parse)
                else:
                    external_links.add(normalized_link)
                    logging.info(f"Found external link: {normalized_link}")


        doc = {
            'url': normalized_url,
            'title': page_title,
            'content': page_content,
            'internal_links': list(internal_links),
            'external_links': list(external_links)
        }

        scrapy_json = {
            'url': normalized_url,
            'title': page_title,
            # 'content': page_content,
            'internal_links': list(internal_links),
            'external_links': list(external_links)
        }


       
        yield scrapy_json

        
        self.index_data_elasticsearch(doc)

    def index_data_elasticsearch(self, data):
        try:

            if not self.es_client.indices.exists(index=self.es_index):
                mapping = {
                    "mappings": {
                        "properties": {
                            "url": {"type": "text"},
                            "title": {"type": "text"},
                            "content": {"type": "text"},
                            "internal_links": {"type": "keyword"},
                            "external_links": {"type": "keyword"}
                        }
                    }
                }
                self.es_client.indices.create(index=self.es_index, body=mapping)
                logging.info(f"Created index with mapping: {self.es_index}")

            self.es_client.index(index=self.es_index, body=data)
            logging.info(f"Data indexed in Elasticsearch: {data['url']}")
        except Exception as e:
            logging.error(f"Failed to index data into Elasticsearch: {str(e)}")

    def is_valid_url(self, url):
        return url.startswith("http") and not (url.startswith("mailto:") or url.startswith("javascript:") or url.startswith("tel:"))

    def is_internal_link(self, url):
        parsed_url = urlsplit(url)
        domain = parsed_url.netloc
        return any(subdomain in domain for subdomain in self.allowed_domains)


class SubdomainScannerBase:
    def __init__(self, domain, output_file, directory, es_host=None, es_port=0, es_scheme=None, es_username=None, es_password=None):
        self.domain = domain
        self.output_file = output_file
        self.directory = directory

        es_host = es_host or os.getenv("ES_HOST")
        es_port = es_port or int(os.getenv("ES_PORT"))
        es_scheme = es_scheme or os.getenv("ES_SCHEME")
        es_username = es_username or os.getenv("ES_USERNAME")
        es_password = es_password or os.getenv("ES_PASSWORD")

        self.es_client = Elasticsearch([{
            "host": es_host, "port": es_port, "scheme": es_scheme
        }], basic_auth=(es_username, es_password), ca_certs="http_ca.crt")

        self.es_index = f"{domain.replace('.', '_')}_index" if domain else "manual_index"

    def check_output(self):
        base_name = os.path.splitext(self.output_file)[0]
        
        output_files = [f"{base_name}.txt", f"{base_name}.json"]

        for file_name in output_files:
            if os.path.exists(file_name):
                with open(file_name, 'r') as file:
                    content = file.read()
                if content:
                    print(f"\nSubdomains have been saved to {file_name}")
                    new_file_path = os.path.join(self.directory, os.path.basename(file_name))
                    os.makedirs(self.directory, exist_ok=True)
                    shutil.move(file_name, new_file_path)
                    print(f"File moved to {new_file_path}")
                else:
                    print(f"The file {file_name} exists but is empty.")
            else:
                print(f"Failed to save subdomains to {file_name}")

    def start_spider(self, file_path):
        with open(file_path, 'r') as file:
            subdomains = file.readlines()

        output_json = os.path.join(self.directory, f"output_{os.path.basename(self.output_file)}.json")
        process = CrawlerProcess(settings={
            'FEEDS': {output_json: {'format': 'json'}},
            'LOG_LEVEL': 'INFO',
            'RETRY_TIMES': 5,
            'USER_AGENT': 'Mozilla/5.0 (compatible; ScrapyBot/1.0; +http://example.com)',
            'DUPEFILTER_DEBUG': True
        })

        logging.info(f"Starting Scrapy Spider for {len(subdomains)} subdomains")
        process.crawl(SubdomainSpider, subdomains=subdomains, es_client=self.es_client, es_index=self.es_index)
        process.start()


class AutoSubdomainScanner(SubdomainScannerBase):
    def enum_subdomain(self):
        try:
            print(f"Starting Amass scan for domain: {self.domain}")
            command = f"amass enum -d {self.domain} -p 80,443 -active -brute -oA {self.output_file} -dir {self.directory}"
            subprocess.run(command, shell=True, check=True)
            print(f"Amass scan completed for domain: {self.domain}")
        except subprocess.CalledProcessError as e:
            print(f"An error occurred during the Amass scan: {str(e)}")


class ManualSubdomainScanner(SubdomainScannerBase):
    def move_subdomain_file(self, subdomains_file):
        file_name_without_ext = os.path.splitext(os.path.basename(subdomains_file))[0]
        new_directory = os.path.join("subdomain_output", "manual", file_name_without_ext).replace('.', '_')
        os.makedirs(new_directory, exist_ok=True)
        new_file_path = os.path.join(new_directory, os.path.basename(subdomains_file))
        shutil.move(subdomains_file, new_file_path)
        print(f"File moved to {new_file_path}")
        return new_file_path


if __name__ == "__main__":
    dns_auto = input("Do you want to Automate DNS Enum? [Y/n]? ").lower()

    if dns_auto == 'n':
        # Manual mode
        subdomains_file = input("Enter the path to the .txt file with the list of subdomains: ")
        domain = input("Enter the domain for indexing: ")
        file_name_without_ext = os.path.splitext(os.path.basename(subdomains_file))[0].replace('.', '_')
        output_file = f"output/{file_name_without_ext}_output"
        output_directory = f"subdomain_output/manual/{domain.replace('.', '_')}/"

        scanner = ManualSubdomainScanner(domain=domain, output_file=output_file, directory=output_directory)
        moved_file_path = scanner.move_subdomain_file(subdomains_file)
        scanner.start_spider(moved_file_path)

    else:
        # Automatic mode
        domain = input("Enter the domain you want to scan: ")
        output_file = f"output/{domain.replace('.', '_')}_output"
        output_directory = f"subdomain_output/manual/{domain.replace('.', '_')}/"

        scanner = AutoSubdomainScanner(domain=domain, output_file=output_file, directory=output_directory)
        scanner.enum_subdomain()
        scanner.check_output()
        scanner.start_spider(output_file + ".txt")
