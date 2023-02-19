import os,glob
def main():
    folder_path = './Repos'
    for filename in glob.glob(os.path.join(folder_path, '*.py')):
        with open(filename, 'r') as f:
            text = f.read()
            print (filename)
            print (len(text))

if __name__ == "__main__":
    main()
