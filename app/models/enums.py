from enum import Enum

class ChannelCode(Enum):
    CALL = "CALL"
    CHAT = "CHAT"
    APP = "APP"
    STORE = "STORE"
    ETC = "ETC"

class ProductLineCode(Enum):
    MOBILE = "MOBILE"
    INTERNET = "INTERNET"
    IPTV = "IPTV"
    TELEPHONE = "TELEPHONE"
    ETC = "ETC"

class StatusCode(Enum):
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    CANCELED = "CANCELED"

class FinalResultCode(Enum):
    DONE = "DONE"
    FOLLOW_UP = "FOLLOW_UP"
    TRANSFERRED = "TRANSFERRED"
    FAILED = "FAILED"

class PriorityCode(Enum):
    LOW = "LOW"
    MID = "MID"
    HIGH = "HIGH"

class SenderType(Enum):
    CUSTOMER = "CUSTOMER"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"

class AlertLevel(Enum):
    LOW = "LOW"
    MID = "MID"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class IndexStatus(Enum):
    PENDING = "PENDING"
    INDEXING = "INDEXING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"