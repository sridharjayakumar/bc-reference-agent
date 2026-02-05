from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Brand Concierge Reference Agent"
    debug: bool = False

    # Brand configuration
    brand_name: str = "Brand Concierge Reference Agent"
    brand_tone: str = "friendly and professional"

    # IMS Authentication (production only)
    ims_client_id: str = ""
    ims_validation_cache_ttl: int = 86400  # 24 hours in seconds
    ims_base_url: str = "https://ims-na1.adobelogin.com"

    class Config:
        env_file = ".env"


settings = Settings()
