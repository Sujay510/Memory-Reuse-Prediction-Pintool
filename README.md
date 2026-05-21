# Memory Reuse Prediction Pintool
A Pintool that uses the given data and predicts the next resuse distance of a given memory
# Features
Each memory address has an array of size 6 acting as buckets.
Through these buckets we store the frequency of the range of reuse distances
Each bucket has a range of the reuse distance:
# Buckets
    Bucket 0: It is a special bucket that has no range it indicates that the memory was used for the   very first time
    Bucket 1: Every distance of range (1,10) gets updated here
    Bucket 2: Every distance of range (11,100) gets updated here
    Bucket 3: Every distance of range (101,1000) gets updated here
    Bucket 4: Every distance of range (1001,10000) gets updated here
    Bucket 5: Every distance of range (10001,100000) gets updated here
    Bucket 6: Every distance greater than 100000 gets updated here

# History Vector
    We maintain a history vector for each memory address. It stores which bucket is being updated.
    FOR EXAMPLE:
     If the reuse distances are 50, 40, 104, 10002, 1000.
     The history array will look something like this history = [B2,B2,B3,B5,B3]
     Most recent bucket updated will have the index n-1 (n being the number of accesses).
# Prediction Algorithm
     We traverse through the hustory vectore and we assign exponential weights to each of the buckets
     using the formula:
        weight(i) = α^(N-1-i)
    α being the decay factor here I have taken it as 0.9.
    i being the index of the bucket in the history vector.
    So the most recent bucket gets the highest weight. In the end all the weights of the each bucket
    are added to give a weight to the bucket.
    So for prediction we simply check the bucket with the highest weight. Meaning it could show the
    most recent and most frequent reuse distance range.
    !!ONE THING TO KEEP IN MIND IS THAT WE PREDICT THE RESUSE DISTANCE RANGE NOT THE EXACT DISTANCE!!
    
# Validation
    To make this validation I thought of using the first 70% of the data inside the history vector to 
    calculate the weights thereby getting the prediction and then verifying it with the remaining 30%
    of the data in the history vector.
    But I couldn't implement this in the pintool itself, because I am new to pintool in the pintool it
    gives the prediction based on 100% of the data rather than splitting it.
    For this I have made a simulation by using a python script, It uses the data from the csv file 
    generated from the pintool, and reconstructs the history vector on its own, there by sometime
    this history vector itself could be inconsistent in the python script. It is an interactive model.

# Requirements
    The device you are using must have intel chip of x86 architecture.(Though other pintool are available but I have implemented in the previously mentioned specs)
    Use Linux OS
# How to use
    Pintool setup:
        1.Download pintool:
        https://www.intel.com/content/www/us/en/developer/articles/tool/pin-a-binary-instrumentation-tool-downloads.html

        (There is Windows OS related pin kit as well; however, this lab will be based on Linux tool)

        2.Unzip the download copy, rename folder to “pin_kit” 
            For example, path to pin_kit is:
            /home/user/pin_kit

        3.Set PIN_ROOT path
            Open ~/.bashrc in editor
            Add the following line to .bashrc
            “export PIN_ROOT= path_to_pinkit/pin_kit/”
            For example: export PIN_ROOT=/home/user/pin_kit
            To reflect variable on terminal use command “source ~/.bashrc”
            Intel Pin provides API to build Pintool, which can be used to analyze any user program (dynamic instrumentation)
            Various examples are given in $PIN_ROOT/source/tools/
            Compiling Pintool using intel pin, sample example given in “path-to-pin-kit/pin_kit/source/tools/MyPinTool”, make file is already there
        4.Run “make”
            It creates “obj-intel64/” folder contains “.so” library object (pintool)
        5.Running pintool with any executable
            $PIN_ROOT/pin -t obj-intel64/MyPinTool.so –  ./path-to-application-executable

    Now replace the MyPinTool.cpp code in the pintool files with the code in this repo.

    Now first go to the directory and run "make clean"
    then run "make" again. For running follow the instructions above.
    Now find the output csv file(mostly in the home directory) and create a new python file
    in the same place and paste the code given in it.
    go back to the directory where you pasted the python file and run "python /filename/.py "
    Now you will have a interactive program running.

# UPDATE
    If anyone is willing to help me regarding implementing the validation in the pintool itself it would be of geat help.
    I also would like to add this may take a lot of space since the history vectors maybe really large sometimes.
    To implement the correct history vector in python script we need to pass the history vectors in
    csv file since it takes input from csv file. Although there could be another method of passing
    this data instead of using the csv file. It would be of great help if anyone could help me implement this part too.
