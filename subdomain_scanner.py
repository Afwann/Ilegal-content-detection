import time
import sublist3r
import os
import shutil
from dotenv import load_dotenv 

class SubdomainScanner:
    def __init__(self, domain, output_file, max_threads=16):
        self.domain = domain
        self.output_file = output_file
        self.max_threads = max_threads

    def enum_subdomain(self):
        try:
            sublist3r.main(
                self.domain, 
                self.max_threads, 
                self.output_file, 
                ports="80,443", 
                silent=True, 
                verbose=True, 
                enable_bruteforce=True, 
                engines=None
            )
        except Exception as e:
            print(f"An error occurred: {str(e)}")

    def check_output(self):
        if os.path.exists(self.output_file):
            with open(self.output_file, 'r') as file:
                content = file.read()
            
            if content:
                print(f"\nSubdomains have been saved to {self.output_file}")

                new_directory = 'subdomain'
                os.makedirs(new_directory, exist_ok=True)
                new_file_path = os.path.join(new_directory, os.path.basename(self.output_file))
                
                shutil.move(self.output_file, new_file_path)
                print(f"File moved to {new_file_path}")
                
            else:
                print(f"The file {self.output_file} exists but is empty.")
        else:
            print(f"Failed to save subdomains to {self.output_file}")

# Usage
if __name__ == "__main__":
    load_dotenv()

    domain = os.getenv("DOMAIN")
    output_file = os.getenv("OUTPUT_FILE")
    max_threads = int(os.getenv("MAX_THREADS"))

    scanner = SubdomainScanner(domain, output_file, max_threads)
    scanner.enum_subdomain()
    time.sleep(5) # Wait for the output to be printed in console
    scanner.check_output()
