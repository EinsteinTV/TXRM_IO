# Introduction

This is the first page of the TXRM IO project. The project was created to make editing and saving TXRM files easier.

TXRM files are created by Zeiss CT scanners and are a type of MS-CFB format.

TXRM IO uses pywin32/pythoncom to read and save streams. Currently, it is possible to edit the number and data of images and metadata, and also add streams as new metadata in the file.

# Features

_setting_ **ANGLE_UNIT** = "degree"\
 The unit to use for thetas.\
 **options** "degree", "rad"

_setting_ **MAX_CONST_DEVIATION** = 0.1\
 The maximal standard deviation in array streams to consider them as constant.\
 **options** float >= 0.0

## _class_ **TXRM_IO**

_method_ **open**(file_path, mode="r", overwrite=False)\
 Opens the file in the given mode.\
 **file_path _str_** String containing the path to the desired file\
 **mode _str_** Which mode to open the file ("r" - readOnly, "w" - readWrite)\
   Defaults to "r"\
 **overwrite _bool_** Flag to decide if the file should be edited in place or create a copy\
 **return** None

_method_ **save**()\
 Only possible when the File was opened in write mode. Saves the streams. Can take some time.\
 **return** None

_method_ **save_as**(file_name)\
 Only possible when the File was opened in write mode. Saves the file under the specified name. Can take some time.\
 **file_name _str_** The name of the new file\
 **return** None

_method_ **close**()\
 Closes the opened file.\
 **return** None

_method_ **add_meta**(name, path, dtype=None, data=None, shape=None)\
 Create a new meta entry and directly read it from the file.\
 **name _str_** The name of the meta-data entry\
 **path _str_** The stream where the metadata is saved\
 **dtype _dtype_** Optional: The datatype of the stream data (uint16, float32, str, bytes) **if not specified _data_ has to be not None**\
 **data _bytes_** Optional: The data to save at this path **if not specified _dtype_ has to be not None and _path_ has to be in file**\
 **shape _tuple_** Optional: The shape of the data to reshape it\
 **return** None

_method_ **get_stream**(stream)\
 Returns the bytes of data in the stream.\
 **stream _str_** The name of the stream in the ole file\
 **return _bytes_** The content of the stream

_method_ **exists**(stream)\
Returns whether or not a stream or storage exists.\
**stream _str_** The path of the stream/storage\
**return _bool_**

_method_ **normalize_images**()\
 Normalizes the image set with the reference image.\
 **return** None

_method_ **reset**()\
 Reverts all eventually made changes to the TXRM object.\
 **return** None

_property_ **images**\
_property_ **thetas**\
_property_ **meta**\
_property_ **reference**\
 Just getter!\
_property_ **distances**\
 Just getter!\
_property_ **shifts**\
 Just getter!\
_property_ **streams**\
 Just getter!\

# Usage

The TXRM IO class can be used with the context manager (recommended) or "classical".

```python
import txrmio

txrmio.MAX_CONST_DEVIATION = 0.2

with txrmio.TXRM_IO("C:/myFile.txrm", "w") as file:
    # Access the images, thetas, and metadata
    images = file.images
    thetas = file.thetas
    meta = file.meta
    
    # Do something with the images and thetas
    new_images, new_thetas = edit_images(images, thetas)
    
    # Replace the old images/thetas with the edited ones
    file.images = new_images
    file.thetas = new_thetas

    # Add new metadata
    file.add_meta("author_name", "AuthorInfo/name", str, data = "MyName".enocde("utf-16"))

    # Add new metadata present in the file
    file.add_meta("new_key", "Existing/Storage/Path", float32, shape=(32,32))

    # Save the file (can take some time, be patient)
    file.save()
```


# License

This software was created by Mario Krake for ISEA at RWTH.

Use at your own risk. Mario Krake and RWTH are not responsible for any kind of damage including hardware and software, data loss, profit loss, or any other kind. By using the software you agree to the terms and conditions.

Monetized and/or uncredited distribution is strongly prohibited.

# Author

Mario Krake, B.Sc.\
Contact through git
