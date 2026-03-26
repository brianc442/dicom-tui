from pathlib import Path
import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import (
    generate_uid,
    ExplicitVRLittleEndian,
    SecondaryCaptureImageStorage,
)


def make_minimal_dicom(path: Path) -> Path:
    """Write a minimal valid DICOM file to `path`. Returns `path`."""
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    ds = Dataset()
    ds.file_meta = file_meta
    ds.preamble = b"\x00" * 128  # required for DICOM magic bytes at offset 128
    ds.is_implicit_VR = False
    ds.is_little_endian = True
    ds.PatientName = "Test^Patient"
    ds.PatientID = "TEST001"
    ds.Modality = "CT"
    ds.StudyDate = "20240101"
    ds.StudyDescription = "Test Study"
    ds.SeriesDescription = "Test Series"
    ds.SOPInstanceUID = generate_uid()
    ds.SOPClassUID = SecondaryCaptureImageStorage
    ds.Rows = 512
    ds.Columns = 512
    ds.BitsAllocated = 16

    pydicom.dcmwrite(str(path), ds)
    return path
