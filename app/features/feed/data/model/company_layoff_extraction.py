from typing import Optional

from pydantic import BaseModel, Field


class CompanyLayoffExtraction(BaseModel):
    company_name: str = Field(description="Company name")
    impact_count: Optional[int] = Field(default=None, description="Impact count i.e No of people laid off or targeted")
    status: str = Field(description="Must be strictly mapped to either 'Confirmed' or 'Rumored'.")
    industry: str = Field(description="Operational sector like Software, Finance, Retail, Entertainment.")
    location: str = Field(description="Geographic scope, e.g., 'San Francisco, CA', 'Remote', or 'Global'.")
    company_url: str = Field(description="Primary root domain of the company, e.g., 'meta.com' for logo pulling.")
    company_category: str = Field(description="Category of the company")
    summary: str = Field(
        description="A brief, clear, exactly two-sentence breakdown detailing reasons and departments impacted.")
    trend_direction: str = Field(
        description="Trajectory direction: 'increasing', 'decreasing', or 'stable' based on context sentiment.")
    approximate_date: Optional[str] = Field(default=None, description="Approximate date the layoff was mentioned")