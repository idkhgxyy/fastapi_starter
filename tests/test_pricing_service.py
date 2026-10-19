"""模型定价中心（pricing_service）单元测试"""

import pytest

from app.models.model_pricing import ModelPricing
from app.services.pricing_service import (
    DEFAULT_PRICINGS,
    estimate_cost_cny,
    get_model_prices,
    invalidate_cache,
    seed_default_pricings,
)


@pytest.fixture(autouse=True)
def _clear_price_cache():
    """每个测试前后清空内存价格缓存，避免串扰"""
    invalidate_cache()
    yield
    invalidate_cache()


class TestSeedDefaultPricings:
    def test_seed_inserts_defaults(self, db_session):
        inserted = seed_default_pricings(db_session)
        assert inserted == len(DEFAULT_PRICINGS)
        names = {r.model_name for r in db_session.query(ModelPricing).all()}
        assert "deepseek-v4.1-flash" in names

    def test_seed_is_idempotent(self, db_session):
        seed_default_pricings(db_session)
        inserted_again = seed_default_pricings(db_session)
        assert inserted_again == 0
        assert (
            db_session.query(ModelPricing).count() == len(DEFAULT_PRICINGS)
        )


class TestGetModelPrices:
    def test_reads_from_db(self, db_session):
        db_session.add(
            ModelPricing(
                model_name="my-custom-model",
                input_price_per_1m=10.0,
                output_price_per_1m=20.0,
            )
        )
        db_session.commit()
        assert get_model_prices(db_session, "my-custom-model") == (10.0, 20.0)

    def test_falls_back_to_settings_when_missing(self, db_session):
        prices = get_model_prices(db_session, "never-seeded-model")
        assert prices == (
            pytest.approx(settings_in_input()),
            pytest.approx(settings_in_output()),
        )

    def test_db_price_overrides_builtin(self, db_session):
        # 表里有记录就用表里的价，哪怕与内置种子/全局兜底不同
        # （用独立模型名，避免与种子数据冲突）
        db_session.add(
            ModelPricing(
                model_name="override-builtin-model",
                input_price_per_1m=99.0,
                output_price_per_1m=199.0,
            )
        )
        db_session.commit()
        assert get_model_prices(db_session, "override-builtin-model") == (99.0, 199.0)

    def test_cache_invalidated_on_demand(self, db_session):
        db_session.add(
            ModelPricing(
                model_name="cached-model", input_price_per_1m=1.0, output_price_per_1m=1.0
            )
        )
        db_session.commit()
        assert get_model_prices(db_session, "cached-model") == (1.0, 1.0)

        # 直接改库后缓存未过期 → 仍是旧值；invalidate 后读到新值
        row = db_session.query(ModelPricing).filter_by(model_name="cached-model").first()
        row.input_price_per_1m = 5.0
        row.output_price_per_1m = 5.0
        db_session.commit()
        assert get_model_prices(db_session, "cached-model") == (1.0, 1.0)
        invalidate_cache()
        assert get_model_prices(db_session, "cached-model") == (5.0, 5.0)


class TestEstimateCostCny:
    def test_uses_db_pricing(self, db_session):
        db_session.add(
            ModelPricing(
                model_name="priced-model", input_price_per_1m=4.0, output_price_per_1m=12.0
            )
        )
        db_session.commit()
        # 1M 输入 + 0.5M 输出 = 4 + 6 = 10 元
        assert estimate_cost_cny(db_session, "priced-model", 1_000_000, 500_000) == pytest.approx(10.0)


def settings_in_input():
    from app.core.config import settings

    return settings.LLM_INPUT_PRICE_PER_1M


def settings_in_output():
    from app.core.config import settings

    return settings.LLM_OUTPUT_PRICE_PER_1M
