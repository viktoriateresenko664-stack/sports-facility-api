import enum


class AccountType(str, enum.Enum):
    USER = "USER"
    EMPLOYEE = "EMPLOYEE"


class FacilityStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    MAINTENANCE = "MAINTENANCE"
    INACTIVE = "INACTIVE"


class EquipmentStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    WARNING = "WARNING"
    OFFLINE = "OFFLINE"
    BROKEN = "BROKEN"


class SensorStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    OFFLINE = "OFFLINE"
    ERROR = "ERROR"


class SensorDataStatus(str, enum.Enum):
    NORMAL = "NORMAL"
    ALERT = "ALERT"
    CRITICAL = "CRITICAL"


class RequestStatus(str, enum.Enum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    ASSIGNED = "ASSIGNED"
    IN_WORK = "IN_WORK"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class TaskStatus(str, enum.Enum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class AvailabilityStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    OFFLINE = "OFFLINE"


class BackgroundJobStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class LogStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class DomainEventStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"
