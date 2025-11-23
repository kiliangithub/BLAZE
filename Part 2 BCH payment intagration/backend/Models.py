# models.py
from typing import Optional
from pydantic import EmailStr
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime, time
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy import ARRAY, Column, Numeric, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import event
from datetime import datetime


class ChildAddressCounter(SQLModel, table=True):
    counter: int = Field(default=1, primary_key=True)

class Bch(SQLModel, table=True):
    address: str = Field(primary_key=True)
    threshold: int = Field(default=None)
    user_id: int = Field(default=None, foreign_key="users.id")
    device_id: int = Field(default=None, foreign_key="devices.id")
    created_at: datetime = Field(default_factory=datetime.now)
    euro_amount: float = Field(default=None, sa_column=Column(Numeric(10, 2)))

class BchPayment(SQLModel, table=True):
    tx_id: str = Field(primary_key=True)
    address: str = Field(index=True)
    amount: int
    euro_amount: float = Field(default=None, sa_column=Column(Numeric(10, 2)))
    usd_amount: float = Field(default=None, sa_column=Column(Numeric(10, 2)))
    reference: str
    description: str
    succeeded_at: datetime
