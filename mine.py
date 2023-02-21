import os,glob
from pathlib import Path
def aggregate(dir_name,output_name):
    
    fulltext = ''
    
    for root, dirs, files in os.walk(dir_name):
        print(root)
        for name in files:
            if name.endswith((".py")):
                with open(os.path.join(root,name), 'r') as f:
                    for line in f:
                        fulltext += line
                    fulltext+="\n"
    fulltext=fulltext[0:len(fulltext)-1]
                
            
    with open(output_name,'w') as aggregateFile:
        aggregateFile.write(fulltext)
    


def main():
    aggregate('.Repos','test.txt')

if __name__ == "__main__":
    main()
