from enum import Enum

class OrderType(str, Enum):
   GTC = "GTC"   #Good Till Cancelled
   GTD = "GTD"   #Good Till Date
   FOK = "FOK"   #Fill Or Kill
   FAK = "FAK"   #Fill And Kill