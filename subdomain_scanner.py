import time
import subprocess
import os
import shutil
from dotenv import load_dotenv

class SubdomainScanner:
    def __init__(self, domain, output_file, directory):
        self.domain = domain
        self.output_file = output_file
        self.directory = directory

    # Amass
    def enum_subdomain(self):
        try:
            print(f"Starting Amass scan for domain: {self.domain}")
            
            command = f"amass enum -d {self.domain}  -p 80,443 -active -brute -oA {self.output_file} -dir {self.directory} "
            subprocess.run(command, shell=True, check=True)

            print(f"Amass scan completed for domain: {self.domain}")
        except subprocess.CalledProcessError as e:
            print(f"An error occurred during the Amass scan: {str(e)}")

    def check_output(self):
        # Generate output file names based on the base name
        base_name = os.path.splitext(self.output_file)[0]
        output_files = [f"{base_name}.txt", f"{base_name}.json"]

        # Check for each output file
        for file_name in output_files:
            if os.path.exists(file_name):
                with open(file_name, 'r') as file:
                    content = file.read()

                if content:
                    print(f"\nSubdomains have been saved to {file_name}")

                    new_directory = 'subdomain_output/ub_ac_id'
                    os.makedirs(new_directory, exist_ok=True)
                    new_file_path = os.path.join(new_directory, os.path.basename(file_name))

                    shutil.move(file_name, new_file_path)
                    print(f"File moved to {new_file_path}")
                else:
                    print(f"The file {file_name} exists but is empty.")
            else:
                print(f"Failed to save subdomains to {file_name}")
# Usage
if __name__ == "__main__":
    load_dotenv()

    domain = os.getenv("DOMAIN") 
    output_file = os.getenv("OUTPUT_FILE")
    directory = os.getenv("DIRECTORY")
    
    scanner = SubdomainScanner(domain, output_file, directory)
    scanner.enum_subdomain()
    time.sleep(5)
    scanner.check_output()
