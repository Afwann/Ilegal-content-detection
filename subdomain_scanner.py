import subprocess
import os
import shutil
from dotenv import load_dotenv
import scrapy
from scrapy.crawler import CrawlerProcess

class SubdomainSpider(scrapy.Spider):
    name = 'subdomain_spider'

    def __init__(self, subdomains):
        self.start_urls = [f"http://{subdomain.strip()}" for subdomain in subdomains]
        self.allowed_domains = [subdomain.strip() for subdomain in subdomains]



    def parse(self, response):
        # Extract full HTML content from the page
        page_content = response.text  # This gets the entire HTML content

        # Optionally, you can extract specific parts of the page, such as title, paragraphs, etc.
        page_title = response.css('title::text').get()  # Get page title
        paragraphs = response.css('p::text').getall()  # Get all paragraph text
        
        # Log and yield the extracted content
        yield {
            'url': response.url,
            'title': page_title,
            'content': page_content,  # Save the full HTML content
            'paragraphs': paragraphs  # Optionally save the paragraph texts
        }

        # Follow each link found on the page to recursively crawl all pages
        links = response.css('a::attr(href)').getall()
        for link in links:
            yield response.follow(link, callback=self.parse)


class SubdomainScanner:
    def __init__(self, domain, output_file, directory):
        self.domain = domain
        self.output_file = output_file
        self.directory = directory

    # Amass Subdomain Enumeration
    def enum_subdomain(self):
        try:
            print(f"Starting Amass scan for domain: {self.domain}")
            
            command = f"amass enum -d {self.domain}  -p 80,443 -active -brute -oA {self.output_file} -dir {self.directory} "
            subprocess.run(command, shell=True, check=True)

            print(f"Amass scan completed for domain: {self.domain}")
        except subprocess.CalledProcessError as e:
            print(f"An error occurred during the Amass scan: {str(e)}")

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
                
    # Using Scrapy to Scrape and Spider Path
    def start_spider(self, file_path):
        with open(file_path, 'r') as file:
            subdomains = file.readlines()

        output_json = os.path.join(self.directory, f"output_{os.path.basename(self.output_file)}.json")

        process = CrawlerProcess(settings={
            'FEEDS': {
                output_json : {'format': 'json'},
            },
        })

        print(f"Starting Scrapy Spider for {len(subdomains)} subdomains")
        process.crawl(SubdomainSpider, subdomains=subdomains)
        process.start()

# Usage
if __name__ == "__main__":
    load_dotenv()

    domain = os.getenv("DOMAIN") 
    output_file = os.getenv("OUTPUT_FILE")
    directory = os.getenv("DIRECTORY")
    
    scanner = SubdomainScanner(domain, output_file, directory)
    scanner.enum_subdomain()
    scanner.check_output()
    scanner.start_spider(f'{directory}{output_file}.txt')
