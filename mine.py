import os,glob
from pathlib import Path
def aggregate():
    folder_path = './Repos'
    fulltext = ''
    for root, dirs, files in os.walk(folder_path):
        for name in files:
            if name.endswith((".py")):
                with open(os.path.join(root,name), 'r') as f:
                    for line in f:
                        fulltext += line
                    fulltext+="\n"
    fulltext=fulltext[0:len(fulltext)-1]
                
            
    with open('aggregateCode.txt','w') as aggregateFile:
        aggregateFile.write(fulltext)
    


def main():
    aggregate()

if __name__ == "__main__":
    main()
