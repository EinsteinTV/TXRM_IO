######################################################################################
#  ______________   ___      ___   ______      ____        ____                      #
# |_____    _____|  \  \    /  /  |  | \  \   |    \      /    |                     #
#       |  |         \  \  /  /   |  |  |  |  |     \    /     |                     #
#       |  |          \  `´  /    |  | /  /   |  |\  \  /  /|  |                     #
#       |  |          /  /\  \    |  |\  \    |  | \  \/  / |  |                     #
#  _    |  |         /  /  \  \   |  | \  \   |  |  \ __ /  |  |                     #
# |_|   |__|        /__/    \__\  |__|  \__\  |__|          |__|                     #
#                                                                                    #
######################################################################################
# This software was created by Mario Krake for ISEA at RWTH.                         #
#                                                                                    #
# Use at your own risk. Mario Krake and RWTH are not responsible for any kind of     #
# damage including hardware and software, data loss, profit loss, or any other kind. #
# By using the software you agree to the terms and conditions.                       #
#                                                                                    #
# Monetized and/or uncredited distribution is strongly prohibited.                   #
######################################################################################

import pythoncom
from win32com.storagecon import STGM_READWRITE, STGM_SHARE_EXCLUSIVE, STGFMT_STORAGE
import numpy as np
from numpy import uint16, uint32, float32
import shutil
import os
from copy import deepcopy


# Self Information
__version__ = "0.2.2"
__future__ = """Planned is to increase the speed and decrease the needed RAM for each file.
Also check for enough space before saving.
Try to find a way to provide functionality to more platforms."""

# Global Flags
ANGLE_UNIT = "degree"
MAX_CONST_DEVIATION = 0.1


class TXRM_IO:
    def __init__(self, file_path, mode="r", overwrite=False):
        if not file_path.lower().endswith(".txrm"):
            file_path = f"{file_path}.txrm"
        self.ifile = None
        self.__mode = mode.lower()
        self.__source_file = file_path
        self.open(file_path, mode.lower(), overwrite)
        self.__stream_list = sorted(self.__build_streams())
        self.__images = None
        self.__thetas = None
        self.__meta = dict()
        self.__const_array_data = dict()
        self.__default = dict()

        # Dict with the Storage/Stream paths of the meta data
        self.__meta_path = {
            "image_width": ["ImageInfo/ImageWidth"],
            "image_height": ["ImageInfo/ImageHeight"],
            "image_data_type": ["ImageInfo/DataType"],  # This one has many same positions
            "number_of_images": ["AcquisitionSettings/TotalImages",
                                "ImageInfo/ImagesTaken",
                                "ImageInfo/NoOfImages",
                                "PositionInfo/NoOfImages",
                                "TemperatureInfo/NoOfImages",
                                "ThermalHistoryInfo/NoOfImages"],
            "pixel_size": ["ImageInfo/pixelsize"],
            "reference_filename": ["ImageInfo/referencefile"],
            "reference_data_type": ["referencedata/DataType"],
            "thetas": ["ImageInfo/Angles"],
            "x_positions": ["ImageInfo/XPosition"],
            "y_positions": ["ImageInfo/YPosition"],
            "z_positions": ["ImageInfo/ZPosition"],
            "x_shifts": ["Alignment/X-Shifts"],
            "y_shifts": ["Alignment/Y-Shifts"]
        }

        self.__load_file()
        # In write mode read neccessary arrays
        if self.__mode == "w":
            self.__load_array_data()
        # Make dict of defaults
        self.__default = {
            "images": deepcopy(self.__images),
            "reference": deepcopy(self.__reference),
            "meta": deepcopy(self.__meta),
            "const": deepcopy(self.__const_array_data),
            "meta_path": deepcopy(self.__meta_path)
        }



# PRIVATE
    def __enter__(self):  # Neccessary for contextmanager
        return self
    
    def __exit__(self, type, value, traceback):  # Neccessary for contextmanager
        self.close()

    def __load_file(self):
        """
        Load the neccessary meta_data from the file
        """
        self.__const_array_data = {
            "ImageInfo/DtoRADistance": self.__read_value("ImageInfo/DtoRADistance", float32), 
            "ImageInfo/StoRADistance": self.__read_value("ImageInfo/StoRADistance", float32)
        }
        num_of_images = self.__read_value("ImageInfo/NoOfImages", uint32)

        self.__meta = {
            "reference_filename": self.__read_value("ImageInfo/referencefile", bytes),
            "reference_data_type": self.__read_value("referencedata/DataType", uint32),

            "image_width": self.__read_value("ImageInfo/ImageWidth", uint32),
            "image_height": self.__read_value("ImageInfo/ImageHeight", uint32),
            "image_data_type": self.__read_value("ImageInfo/DataType", uint32),
            "number_of_images": num_of_images,
            "pixel_size": self.__read_value("ImageInfo/pixelsize", float32),
            "thetas": self.__read_value("ImageInfo/Angles", float32),

            "x_positions": self.__read_value("ImageInfo/XPosition", float32),
            "y_positions": self.__read_value("ImageInfo/YPosition", float32),
            "z_positions": self.__read_value("ImageInfo/ZPosition", float32),
            "x_shifts": self.__read_value("Alignment/X-Shifts", float32),
            "y_shifts": self.__read_value("Alignment/Y-Shifts", float32)
        }
        if self.__meta["reference_data_type"] == 10:
            ref_dtype = float32
        elif self.__meta["reference_data_type"] == 5:
            ref_dtype = uint16
        else:
            ref_dtype = np.nan
        
        if self.__meta["image_data_type"] == 10:
            image_dtype = float32
        elif self.__meta["image_data_type"] == 5:
            image_dtype = uint16
        else:
            image_dtype = np.nan
        
        if ANGLE_UNIT=="rad":
            self.__meta["thetas"] = np.radians(self.__meta["thetas"])
        
        self.__thetas = self.__meta["thetas"]
        shape = (self.__meta["image_height"], self.__meta["image_width"])
        self.__images = np.empty(shape=(num_of_images, *shape), dtype=image_dtype)
        for i in range(1, num_of_images+1):
            data = self.get_stream(f"ImageData{(i+99)//100}/Image{i}")
            self.__images[i-1] = np.frombuffer(data, dtype=image_dtype).reshape(shape)
        # Also get the reference image
        self.__reference = np.frombuffer(self.get_stream("ReferenceData/Image"),
                                        dtype=ref_dtype).reshape(shape)
        
    def __read_value(self, stream, dtype):
        if dtype == str or dtype == bytes:
            return self.get_stream(stream)
        else:
            value =  np.frombuffer(self.get_stream(stream), dtype=dtype)
            if value.size == 1:
                return value[0]
            else:
                return value

    def __load_array_data(self):
        """
        Load all array data with the same size as num_of_images for saving later. JUST in write mode.
        """
        num_of_images = self.__meta["number_of_images"]

        for s in self.__stream_list:
            temp_paths = [p for l in self.__meta_path.values() for p in l]
            try:
                data_f = np.frombuffer(self.get_stream(s), dtype=float32)
                if not s in temp_paths and data_f.size == num_of_images:
                    if np.std(data_f, ddof=1) > MAX_CONST_DEVIATION:
                        self.__meta[f"array_{s.split('/')[-1]}"] = data_f
                        self.__meta_path[f"array_{s.split('/')[-1]}"] = [s]
                    else:
                        self.__const_array_data[s] = data_f
            except:
                pass
    
    def __build_streams(self, root=None, path=[], tree=[]):
        """
        Iterative function to generate list of streams
        """
        modus = STGM_READWRITE|STGM_SHARE_EXCLUSIVE
        if not root:
            root = self.ifile

        for element in root.EnumElements():
            path.append(element[0])
            typ = element[1]
            if typ==1:
                strg = root.OpenStorage(element[0], None, modus, None)
                tree = self.__build_streams(strg, list(path), tree)
            else:
                tree.append("/".join(path))
            path = path[:-1]
        return tree
    
    def __recursive_writing(self, stream_path, data):
        """
        Approach to automatically open storage paths till stream and save data
        data has to be bytes
        """
        if not isinstance(data, bytes):
            raise TypeError("data has to be bytes")
        
        stream_path = stream_path.split("/")
        stream = stream_path[-1]
        stream_path = stream_path[:-1]
        istorages = [self.ifile]
        modus = STGM_READWRITE|STGM_SHARE_EXCLUSIVE
        for path in stream_path:
            istorages.append(istorages[-1].OpenStorage(path, None, modus, None))
        istream = istorages[-1].OpenStream(stream, None, modus, 0)
        istream.SetSize(len(data))
        istream.Write(data)




# PUBLIC
    def get_stream(self, stream):
        stream = stream.split("/")
        stream_path = stream[:-1]
        stream = stream[-1]
        istorage_0 = self.ifile
        modus = STGM_READWRITE|STGM_SHARE_EXCLUSIVE
        for i, path in enumerate(stream_path, 1):
            # Locals workaround is faster than list allocation
            locals()[f"istorage_{i}"] = locals()[f"istorage_{i-1}"].OpenStorage(path, None, modus, None)
        istream = locals()[f"istorage_{i}"].OpenStream(stream, None, modus)
        return istream.Read(istream.Stat()[2])
    
    def exists(self, stream):
        if stream in self.__stream_list:
            return True
        else:
            for s in self.__stream_list:
                if s.startswith(stream+"/"):
                    return True
            else:
                return False

    def add_meta(self, name, path, dtype=None, data=None, shape=None):
        self.__meta_path[name] = [path]
        if not data and not shape:
            raise ValueError("At least one of data and dtype has to be specified")
        if not data:
            data = self.__read_value(path, dtype)
        if shape:
            data = data.reshape(shape)
        self.meta[name] = data

    def normalize_images(self):
        self.__images = self.__images/self.__reference
    
    def reset(self):
        self.__images = self.__default["images"]
        self.__reference = self.__default["reference"]
        self.__meta = self.__default["meta"]
        self.__thetas = self.__meta["thetas"]
        self.__const_array_data = self.__default["const"]
        self.__meta_path = self.__default["meta_path"]

    def open(self, file_path, mode="r", overwrite=False):
        if mode == "w" and not overwrite:
            old = file_path
            # TODO: Move to save and use save_as?
            file_path = f"{file_path.removesuffix('.txrm')}_edit.txrm"
            shutil.copy(old, file_path)
            self.__source_file = file_path
        # Open File
        modus = STGM_READWRITE|STGM_SHARE_EXCLUSIVE
        self.ifile = pythoncom.StgOpenStorageEx(file_path, modus, STGFMT_STORAGE, 0,
                                                pythoncom.IID_IStorage)

    def close(self):  # Close OLE file and remove ifile from scope
        del self.ifile
        
    def save(self):
        # NOTE: Do I have to close OLE before making changes?
        mode=STGM_READWRITE|STGM_SHARE_EXCLUSIVE
        data_failure = False
        if self.__mode != "w":
            raise IOError("File can not be saved in read mode!")
        else:
            num_of_images = self.__images.shape[0]
            num_of_image_storages = int(np.ceil(num_of_images/100))

            for key, value in self.__meta.items():
                if (key.startswith("array_") or key in ["thetas", "x_positions", "y_positions",
                                                        "z_positions", "x_shifts", "y_shifts"]
                ) and value.size<num_of_images:
                    print(key, "does not have the right length of", num_of_images, "is", value.size, flush=True)
                    data_failure = True
                # NOTE: Change maybe to add all the print lines to the ValueError?
            if data_failure:
                raise ValueError("Some Arrays have no the right length!")
        
        print("Saving file, please wait | ", end="", flush=True)
        # First remove all image storages not needed and also the last filled one to remove images
        for i in range(num_of_image_storages+1, num_of_image_storages+10):
            if self.exists(f"ImageData{i}"):
                self.ifile.DestroyElement(f"ImageData{i}")
            else:
                # There should not be empty spaces between
                break

        # Save images ##################################################################
        current_image_index = 1
        for i in range(1, num_of_image_storages+1):
            # Create image storage or open one
            if self.exists(f"ImageData{i}"):
                istorage = self.ifile.OpenStorage(f"ImageData{i}", None, mode, None)
            else:
                istorage = self.ifile.CreateStorage(f"ImageData{i}", mode, 0)
            
            # Save 100 images per storage
            for _ in range(100):
                if current_image_index>num_of_images:
                    break
                if self.exists(f"ImageData{i}/Image{current_image_index}"):
                    istream = istorage.OpenStream(f"Image{current_image_index}", None, mode, 0)
                else:
                    istream = istorage.CreateStream(f"Image{current_image_index}", mode, 0)
                istream.Write(self.__images[current_image_index-1].tobytes())
                current_image_index += 1

        # Edit image infos #############################################################
        # NOTE: TESTED, SLOW
        if ANGLE_UNIT=="rad":
            self.__meta["thetas"] = np.degrees(self.__meta["thetas"])
        for key, path_list in self.__meta_path.items():
            for path in path_list:
                data = np.array(self.__meta[key]).tobytes()
                self.__recursive_writing(path, data)
        
        for key, value in self.__const_array_data.items():
            if value.size < num_of_images:
                data = np.pad(value, (0, num_of_images-value.size), "mean").tobytes()
            else:
                data = value[:num_of_images].tobytes()
            self.__recursive_writing(key, data)
        print("Ready")

    def save_as(self, file_name):
        if self.__mode != "w":
            raise IOError("File can not be saved in read mode!")
        if not file_name.lower().endswith(".txrm"):
            file_name = f"{file_name}.txrm"
        if not ("\\" in file_name or "/" in file_name):
            file_path = os.path.join(os.path.dirname(self.__source_file), file_name)
        else:
            if not os.path.exists(os.path.dirname(file_name)):
                print("File path not existing, fallback to dir:", os.path.dirname(self.__source_file))
                file_path = os.path.join(os.path.dirname(self.__source_file), os.path.basename(file_name))
            else:
                file_path = file_name
        shutil.copy(self.__source_file, file_path)
        # Open File
        modus = STGM_READWRITE|STGM_SHARE_EXCLUSIVE
        self.ifile = pythoncom.StgOpenStorageEx(file_path, modus, STGFMT_STORAGE, 0,
                                                pythoncom.IID_IStorage)
        self.save()
        self.ifile = pythoncom.StgOpenStorageEx(self.__source_file, modus, STGFMT_STORAGE, 0,
                                                pythoncom.IID_IStorage)



# PROPERTIES
    @property
    def thetas(self):
        return self.__thetas

    @thetas.setter
    def thetas(self, value):
        self.meta["thetas"] = value
        self.__thetas = value

    @property
    def meta(self):
        return self.__meta
    
    @meta.setter
    def meta(self, value):
        if not isinstance(value, dict) or self.__meta.keys() != value.keys():
            raise ValueError("Use add_meta to add meta-data to the object!")
        self.__meta = value
        self.thetas = self.__meta["thetas"]
        self.__meta["number_of_images"] = self.__images.shape[0]

    @property
    def images(self):
        return self.__images
    
    @images.setter
    def images(self, value):
        image_dtype = float32 if self.__meta["image_data_type"] == 10 else uint16
        self.__images = value.astype(image_dtype)
        self.__meta["number_of_images"] = self.__images.shape[0]
    
    @property
    def distances(self):
        """
        Returns the distance of detector to battery and battery to source
        (DtoRA, StoRA)
        """
        return (self.__const_array_data["ImageInfo/DtoRADistance"][0], -self.__const_array_data["ImageInfo/StoRADistance"][0])
    
    @property
    def reference(self):
        return self.__reference
    
    @property
    def shifts(self):
        return self.__meta["x_shifts"], self.__meta["y_shifts"]

    @property
    def streams(self):
        return self.__stream_list