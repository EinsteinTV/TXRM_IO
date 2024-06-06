######################################################################################
#  ______________   ___      ___   ______      ____        ____    __     _______    #
# |_____    _____|  \  \    /  /  |  | \  \   |    \      /    |  |  |  /   ___   \  #
#       |  |         \  \  /  /   |  |  |  |  |     \    /     |  |  |  |  |   |  |  #
#       |  |          \  `´  /    |  | /  /   |  |\  \  /  /|  |  |  |  |  |   |  |  #
#       |  |          /  /\  \    |  |\  \    |  | \  \/  / |  |  |  |  |  |   |  |  #
#  _    |  |         /  /  \  \   |  | \  \   |  |  \ __ /  |  |  |  |  |  |___|  |  #
# |_|   |__|        /__/    \__\  |__|  \__\  |__|          |__|  |__|  \ _______ /  #
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
__version__ = "0.5.0"
__future__ = """Planned is to increase the speed and decrease the needed RAM for each file.
Also check for enough space before saving.
Try to find a way to provide functionality to more platforms.
Rewrite some code.
Add functionality to IO, like Dates and Motorpositions.
Possibility to reduce file size.
Possibility for faster and optimized writing."""
__issues__ = """Can't reduce filesize.
Can't increase number of images for every file, much manual tweaking."""

# Global Flags
ANGLE_UNIT = "degree"
MAX_CONST_DEVIATION = 0.1
__AUTO_FORMAT_DATES = True
MAKE_BACKUP = False

class OLE_Base:
    """
    Base class for OLE/CBF files.
    Provides read and write methods, does not convert, prepare or handle data (structure)
    """

    def __init__(self, file_path, mode="r"):
        self.file_path = file_path
        self.MODUS = STGM_READWRITE|STGM_SHARE_EXCLUSIVE
        self.ifile = None
        self.__mode =  "w" if mode.lower() == "w" else "r"

    def __del__(self):
        self.close()

    def __enter__(self):  # Neccessary for contextmanager
        self.open()
        return self
    
    def __exit__(self, type, value, traceback):  # Neccessary for contextmanager
        self.close()
    
    def open(self):
        try:
            self.ifile = pythoncom.StgOpenStorageEx(self.file_path, self.MODUS, STGFMT_STORAGE, 0,
                                                pythoncom.IID_IStorage)
        except:
            self.ifile = pythoncom.StgCreateStorageEx(self.file_path, self.MODUS, STGFMT_STORAGE, 0,
                                                pythoncom.IID_IStorage)
        self.__streams = sorted(self._build_streams())

    def close(self):  # Remove ifile from scope
        if hasattr(self,"ifile"):
            del self.ifile
        if hasattr(self, "__streams"):
            self.__streams = []
            del self.__streams
    
    def _build_streams(self, root=None, path=[], tree=[], storages=False):
        """
        Iterative function to generate list of streams
        """
        modus = STGM_READWRITE|STGM_SHARE_EXCLUSIVE
        if not root:
            root = self.ifile
            if len(path)>0:
                path = []
                tree = []

        for element in root.EnumElements():
            path.append(element[0])
            typ = element[1]
            if typ==1:
                strg = root.OpenStorage(element[0], None, modus, None)
                tree = self._build_streams(strg, list(path), tree, storages)
            else:
                tree.append("/".join(path))
            path = path[:-1]
        if storages and not root==self.ifile:
            # Append also empty Storages
            tree.append("/".join(path))
        del path
        return tree
    
    def remove_stream(self, stream):
        """Removes the given stream and returns (True, None) if sucessfull 
        and (False, Error) when failed
        NOTE: Currently this does not change the filesize"""
        if self.__mode=="r":
            raise Exception("Can't remove streams in read mode")
        stream = stream.split("/")
        stream_path = stream[:-1]
        stream = stream[-1]
        istorages = [self.ifile]
        for path in stream_path:
            try:
                istorages.append(istorages[-1].OpenStorage(path, None, self.MODUS, None))
            except Exception as e:
                return False, e
        try:
            istorages[-1].DestroyElement(stream)
        except Exception as e:
            return False, e
        if stream in self.__streams:
            self.__streams.remove(stream)
        else:
            streams = deepcopy(self.__streams)
            for s in streams:
                if s.startswith(stream+"/"):
                    self.__streams.remove(s)
        return True, None
        
    def clear_file(self, skip_dialog_for_safety=False):
        """Clears all stream and storage handles.
        Usese remove_stream internally.
        NOTE: This does not effect the file size
        skip_dialog_for_safety (bool): Small dialog to not accidently leave a clear_file in code"""
        
        if self.__mode=="r":
            raise Exception("Can't clear file in read mode")

        if not skip_dialog_for_safety:
            do_clear = input("Do you really want to delete all Streams and Storages? [y/N]: ")
            if not do_clear.lower() == "y":
                print("Abort")
                return

        streams = deepcopy(self.__streams)
        i = 0
        for stream in streams:
            sucess, err = self.remove_stream(stream)
            if not sucess:
               print("Error removing:", stream, err)
               i+=1
            if i>6:
                exit()
        
        storages = self.__build_streams(storages=True)
        for storage in storages:
            self.remove_stream(storage)

    def exists(self, stream):
        """Returns if a given stream was found in the stream building process"""
        if stream in self.__streams:
            return True
        else:
            for s in self.__streams:
                if s.startswith(stream+"/"):
                    return True
            else:
                return False

    def read_stream(self, stream):
        """Returns the bytestring of a given stream, if no stream was found or an error occured returns b'' """
        stream = stream.split("/")
        stream_path = stream[:-1]
        stream = stream[-1]
        istorages = [self.ifile]
        for path in stream_path:
            try:
                istorages.append(istorages[-1].OpenStorage(path, None, self.MODUS, None))
            except:
                return b""
        try:
            istream = istorages[-1].OpenStream(stream, None, self.MODUS, 0)
        except:
            return b""
        try:
            return istream.Read(istream.Stat()[2])
        except:
            return b""

    def write_stream(self, stream_path, data):
        """
        Approach to automatically open storage paths till stream and save data.
        data has to be bytes
        """
        if self.__mode=="r":
            raise Exception("Can't write in read mode")
        if not isinstance(data, bytes):
            raise TypeError("data has to be bytes")
        if data == b"":
            print("Empty Data for", stream_path)
        
        stream_path_ = stream_path.split("/")
        stream = stream_path_[-1]
        stream_path_ = stream_path_[:-1]
        istorages = [self.ifile]
        for path in stream_path_:
            try:
                istorages.append(istorages[-1].OpenStorage(path, None, self.MODUS, None))
            except:
                istorages.append(istorages[-1].CreateStorage(path, self.MODUS, 0))
        try:
            istream = istorages[-1].OpenStream(stream, None, self.MODUS, 0)
        except:
            istream = istorages[-1].CreateStream(stream, self.MODUS, 0)
        istream.SetSize(len(data))
        istream.Write(data)
        if not stream_path_ in self.__streams:
            self.__streams.append(stream_path_)

    @property
    def streams(self):
        """Returns a list of all found streams in the stream build process"""
        return self.__streams

# For old code to work
TXRM_Handle = OLE_Base

###################################################################################################

class TXRM_array:
    """
    This class does just read images and angles but does not load the whole imagedata into memory.
    You can slice the array to get special image indices as well as the angles.
    It holds the file handle!
    To get other data use read_stream and handle the bytes yourself
    """
    def __init__(self, file_path, normalize=False):
        self.file_path = file_path
        # self.img_shape = shape
        self.normalize = normalize
        # Open File
        self.MODUS = STGM_READWRITE|STGM_SHARE_EXCLUSIVE
        self.ifile = pythoncom.StgOpenStorageEx(file_path, self.MODUS, STGFMT_STORAGE, 0,
                                                pythoncom.IID_IStorage)
        self.num_of_images = int.from_bytes(self.read_stream("ImageInfo/NoOfImages"), "little")
        if normalize:
            self.ref = np.frombuffer(self.read_stream(f"ReferenceData/Image"), dtype=float32).reshape(self.img_shape)
        
        width = int.from_bytes(self.read_stream("ImageInfo/ImageWidth"), "little")
        height = int.from_bytes(self.read_stream("ImageInfo/ImageHeight"), "little")
        self.img_shape = (height, width)
        data_type = int.from_bytes(self.read_stream("ImageInfo/DataType"), "little")
        self.img_dtype = np.float32 if data_type == 10 else np.uint16

    def __enter__(self):  # Neccessary for contextmanager
        return self
    
    def __exit__(self, type, value, traceback):  # Neccessary for contextmanager
        del self.ifile

    def __del__(self):  # Remove ifile from scope
        if hasattr(self, "ifile"):
            del self.ifile
    
    def read_stream(self, stream)->bytes:
        stream = stream.split("/")
        stream_path = stream[:-1]
        stream = stream[-1]
        istorages = [self.ifile]
        for path in stream_path:
            try:
                istorages.append(istorages[-1].OpenStorage(path, None, self.MODUS, None))
            except:
                return b""
        try:
            istream = istorages[-1].OpenStream(stream, None, self.MODUS, 0)
        except:
            return b""
        try:
            return istream.Read(istream.Stat()[2])
        except:
            return b""

    def __getitem__(self, val):
        if type(val)==tuple and isinstance(val[0], (int, tuple, slice, list, np.ndarray)):
            val, *other = val
        idx = np.arange(self.num_of_images)[val]

        if isinstance(idx, (int, np.int64, np.int32)):
            return np.frombuffer(self.read_stream(f"ImageData{int(np.ceil((idx+1)/100))}/Image{idx+1}"), dtype=self.img_dtype).reshape(self.img_shape)
        out = np.empty((idx.size, *self.img_shape), dtype=self.img_dtype)
        for i,j in enumerate(idx):
            out[i] = np.frombuffer(self.read_stream(f"ImageData{int(np.ceil((j+1)/100))}/Image{j+1}"), dtype=self.img_dtype).reshape(self.img_shape)
        
        return (out/self.ref) if self.normalize else out
    
    def __len__(self):
        return self.num_of_images
    
    @property
    def size(self):
        return self.num_of_images
    
    def shape(self):
        return (self.num_of_images, *self.img_shape)

    @property
    def angles(self):
        if ANGLE_UNIT=="rad":
            return np.deg2rad(np.frombuffer(self.read_stream("ImageInfo/Angles"), float32))
        else:
            return np.frombuffer(self.read_stream("ImageInfo/Angles"), float32)

###################################################################################################

class TXRM_IO(OLE_Base):
    def __init__(self, file_path, mode="r", overwrite=False):
        self.MODUS = STGM_READWRITE|STGM_SHARE_EXCLUSIVE
        if not file_path.lower().endswith(".txrm"):
            file_path = f"{file_path}.txrm"
        
        self.__source_file = file_path
        self.__overwrite = overwrite
        self.__mode = "w" if mode.lower()=="w" else "r"
        
        
        self.__images = None
        self.__angles = None
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
            "pixel_size": ["ImageInfo/PixelSize"],
            "cam_pixel_size": ["ImageInfo/CamPixelSize"],
            "optical_magnification": ["ImageInfo/OpticalMagnification"],
            "binning": ["ImageInfo/CameraBinning"],
            "reference_filename": ["ImageInfo/ReferenceFile"],
            "reference_data_type": ["referencedata/DataType"],
            "angles": ["ImageInfo/Angles"],
            "x_positions": ["ImageInfo/XPosition"],
            "y_positions": ["ImageInfo/YPosition"],
            "z_positions": ["ImageInfo/ZPosition"],
            "x_shifts": ["Alignment/X-Shifts"],
            "y_shifts": ["Alignment/Y-Shifts"]
        }
        # Dict with pathes of arrays with 40bytes per entry
        self.__big_path = {
            "dates": "ImageInfo/Dates",                     # 23 Bytes date + 13 \x00 + \xb5 + 3 \x00
            "motor": "PositionInfo/MotorPositions",
            "motor_raw": "PositionInfo/RawMotorPositions",
            "motor_ideal": "PositionInfo/MotorPositionsIdeal",
            "units": "PositionInfo/AxisUnits",
            "axis_names": "PositionInfo/AxisNames"
        }


        

# PRIVATE
    def __enter__(self):  # Neccessary for contextmanager
        self.open()
        self.__load_file()
        if self.__mode == "w":
            self.__load_array_data()
        return self

    def __read_value(self, stream, dtype):
        if dtype == str or dtype == bytes:
            return self.read_stream(stream)
        else:
            value =  np.frombuffer(self.read_stream(stream), dtype=dtype)
            if value.size == 1:
                return value[0]
            else:
                return value

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
            "reference_filename": self.__read_value("ImageInfo/ReferenceFile", bytes),
            "reference_data_type": self.__read_value("referencedata/DataType", uint32),

            "image_width": self.__read_value("ImageInfo/ImageWidth", uint32),
            "image_height": self.__read_value("ImageInfo/ImageHeight", uint32),
            "image_data_type": self.__read_value("ImageInfo/DataType", uint32),
            "number_of_images": num_of_images,
            "pixel_size": self.__read_value("ImageInfo/PixelSize", float32),
            "cam_pixel_size": self.__read_value("ImageInfo/CamPixelSize", float32),
            "optical_magnification": self.__read_value("ImageInfo/OpticalMagnification", float32),
            "binning": self.__read_value("ImageInfo/CameraBinning", uint32),
            "angles": self.__read_value("ImageInfo/Angles", float32),

            "x_positions": self.__read_value("ImageInfo/XPosition", float32),
            "y_positions": self.__read_value("ImageInfo/YPosition", float32),
            "z_positions": self.__read_value("ImageInfo/ZPosition", float32),
            "x_shifts": self.__read_value("Alignment/X-Shifts", float32),
            "y_shifts": self.__read_value("Alignment/Y-Shifts", float32)
        }
        if self.__meta["reference_data_type"] == 10:
            ref_dtype = float32  # float16?
        elif self.__meta["reference_data_type"] == 5:
            ref_dtype = uint16
        else:
            ref_dtype = np.nan
        
        if self.__meta["image_data_type"] == 10:
            image_dtype = float32  # float16?
        elif self.__meta["image_data_type"] == 5:
            image_dtype = uint16
        else:
            image_dtype = np.nan
        
        if ANGLE_UNIT=="rad":
            self.__meta["angles"] = np.radians(self.__meta["angles"])
        
        self.__angles = self.__meta["angles"]
        shape = (self.__meta["image_height"], self.__meta["image_width"])
        self.__images = np.empty(shape=(num_of_images, *shape), dtype=image_dtype)
        for i in range(1, num_of_images+1):
            data = self.read_stream(f"ImageData{(i+99)//100}/Image{i}")
            self.__images[i-1] = np.frombuffer(data, dtype=image_dtype).reshape(shape)
        # Also get the reference image
        self.__reference = np.frombuffer(self.read_stream("ReferenceData/Image"),
                                        dtype=ref_dtype).reshape(shape)
        
    def __load_big(self):
        """
        Load data saved in big_paths and restructure to a better format
        """
        return "NOT READY"
        self.__dates = Big_obj("dates", values=self.__read_value("ImageInfo/Date", bytes))
        self.__motors = Big_obj("motor", values=self.__read_value("PositionInfo/MotorPositions", float32),\
                                        raw=self.__read_value("PositionInfo/RawMotorPositions", float32),\
                                        ideal=self.__read_value("PositionInfo/MotorPositionsIdeal", float32),\
                                        axis=self.__read_value("PositionInfo/AxisNames", bytes),\
                                        units=self.__read_value("PositionInfo/AxisUnits", bytes))

    def __load_array_data(self):
        """
        Load all array data with the same size as num_of_images for saving later. JUST in write mode.
        """
        num_of_images = self.__meta["number_of_images"]

        for s in self.__stream_list:
            temp_paths = [p for l in self.__meta_path.values() for p in l]
            try:
                data_f = np.frombuffer(self.read_stream(s), dtype=float32)
                if not s in temp_paths and data_f.size == num_of_images:
                    if np.std(data_f, ddof=1) > MAX_CONST_DEVIATION:
                        self.__meta[f"array_{s.split('/')[-1]}"] = data_f
                        self.__meta_path[f"array_{s.split('/')[-1]}"] = [s]
                    else:
                        self.__const_array_data[s] = data_f
            except:
                pass
    
# PUBLIC
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
        if not MAKE_BACKUP:
            print("No Backup was created to reset, please set MAKE_BACKUP to True")
            return
        self.__images = deepcopy(self.__default["images"])
        self.__reference = deepcopy(self.__default["reference"])
        self.__meta = deepcopy(self.__default["meta"])
        self.__angles = deepcopy(self.__meta["angles"])
        self.__const_array_data = deepcopy(self.__default["const"])
        self.__meta_path = deepcopy(self.__default["meta_path"])

    def open(self):
        if self.__mode == "w" and not self.__overwrite:
            old = self.__source_file
            file_path = f"{self.__source_file.removesuffix('.txrm')}_edit.txrm"
            shutil.copy(old, file_path)
            self.__source_file = file_path
        # Open File
        modus = STGM_READWRITE|STGM_SHARE_EXCLUSIVE
        self.ifile = pythoncom.StgOpenStorageEx(self.__source_file, modus, STGFMT_STORAGE, 0,
                                                pythoncom.IID_IStorage)
        self.__stream_list = sorted(self._build_streams())
        
        if MAKE_BACKUP:
            # Make dict of defaults
            self.__default = {
                "images": deepcopy(self.__images),
                "reference": deepcopy(self.__reference),
                "meta": deepcopy(self.__meta),
                "const": deepcopy(self.__const_array_data),
                "meta_path": deepcopy(self.__meta_path)
            }


    def save(self):
        mode=STGM_READWRITE|STGM_SHARE_EXCLUSIVE
        data_failure = False
        if self.__mode != "w":
            raise IOError("File can not be saved in read mode!")
        else:
            num_of_images = self.__images.shape[0]
            num_of_image_storages = int(np.ceil(num_of_images/100))

            for key, value in self.__meta.items():
                if (key.startswith("array_") or key in ["angles", "x_positions", "y_positions",
                                                        "z_positions", "x_shifts", "y_shifts"]
                ) and value.size<num_of_images:
                    print(key, "does not have the right length of", num_of_images, "is", value.size, flush=True)
                    data_failure = True
                # NOTE: Change maybe to add all the print lines to the ValueError?
            if data_failure:
                raise ValueError("Some Arrays have not the right length!")
        
        print("Saving file, please wait | ", end="", flush=True)
        # First remove all image storages not needed and also the last filled one to remove images
        for i in range(num_of_image_storages, num_of_image_storages+10):
            if self.exists(f"ImageData{i}"):
                self.remove_stream(f"ImageData{i}")
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
            self.__meta["angles"] = np.degrees(self.__meta["angles"])
        for key, path_list in self.__meta_path.items():
            for path in path_list:
                data = np.array(self.__meta[key]).tobytes()
                print("Saving:", path)
                self.write_stream(path, data)
        
        for key, value in self.__const_array_data.items():
            if value.size < num_of_images:
                data = np.pad(value, (0, num_of_images-value.size), "mean").tobytes()
            else:
                data = value[:num_of_images].tobytes()
            print("Saving",key)
            self.write_stream(key, data)
        print("Ready")

    def save_as(self, file_name):
        if self.__mode == "r":
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
        tmp_streams = self.__stream_list
        self.__stream_list = sorted(self.__build_streams())
        self.save()
        self.__stream_list = tmp_streams
        self.ifile = pythoncom.StgOpenStorageEx(self.__source_file, modus, STGFMT_STORAGE, 0,
                                                pythoncom.IID_IStorage)


# PROPERTIES
    @property
    def thetas(self):
        print("WARNING: Change to angles instead of thetas")
        return self.__angles
    @thetas.setter
    def thetas(self, value):
        self.meta["angles"] = value
        self.__angles = value

    @property
    def angles(self):
        return self.__angles
    @angles.setter
    def angles(self, value):
        self.meta["angles"] = value
        self.__angles = value

    @property
    def meta(self):
        return self.__meta
    @meta.setter
    def meta(self, value):
        if not isinstance(value, dict) or self.__meta.keys() != value.keys():
            raise ValueError("Use add_meta to add meta-data to the object!")
        self.__meta = value
        self.angles = self.__meta["angles"]
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
    
    @property
    def dates(self):
        """
        Returns the dates for each projection
        """
        return self.__dates.get_values()
    @dates.setter
    def dates(self, data):
        self.__dates.setter(data)
    
    @property
    def motors(self):
        """
        Return the Motorspostionarrays as a tuple of (axis_names, units, motors, raw_motors, ideal_motors)
        """
        return self.__motors.get_values()
    @motors.setter
    def motors(self, data):
        self.__motors.setter(data)


