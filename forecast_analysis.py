from __future__ import annotations
"""
Forecast Skill - Multi-model forecasting with automatic model selection
"""
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import warnings
warnings.filterwarnings('ignore')

from skill_framework import skill, SkillParameter, SkillInput, SkillOutput


@skill(
    name="Forecast Analysis",
    llm_name="forecast_analysis",
    description="Generate intelligent forecasts using best-fit model selection with automatic model optimization",
    capabilities="Provides multi-model forecasting with automatic selection of best-performing algorithm. Supports linear regression, moving average, and other forecasting models. Generates confidence intervals, trend analysis, and seasonality detection. Creates professional visualizations with KPIs, charts, and insights.",
    limitations="Requires minimum 12 historical data points. Limited to 36 months forecast horizon. Assumes monthly granularity (max_time_month). Performance depends on data quality and historical patterns.",
    example_questions="What will sales be over the next 6 months? Can you forecast volume for Q1 2024? Show me a 12-month revenue projection with confidence intervals. What's the expected growth trend for the next quarter?",
    parameter_guidance="Select metric to forecast (sales, volume, etc.). Choose forecast steps (1-36 months, default 6). Optionally filter by date range or apply dimensional filters. The skill automatically selects the best forecasting model based on historical performance.",
    parameters=[
        SkillParameter(
            name="metric",
            constrained_to="metrics",
            description="The metric to forecast"
        ),
        SkillParameter(
            name="forecast_steps",
            description="Number of periods to forecast (months)",
            default_value=6
        ),
        SkillParameter(
            name="start_date",
            description="Start date for training data (YYYY-MM-DD)",
            default_value="2022-01-01"
        ),
        SkillParameter(
            name="other_filters",
            constrained_to="filters",
            description="Additional filters to apply to the data"
        ),
        SkillParameter(
            name="confidence_level",
            description="Confidence level for prediction intervals",
            default_value=0.95
        ),
        SkillParameter(
            name="max_prompt",
            parameter_type="prompt",
            description="Prompt being used for max response.",
            default_value="Answer user question in 30 words or less using following facts:\n{{facts}}"
        ),
        SkillParameter(
            name="insight_prompt",
            parameter_type="prompt",
            description="Prompt being used for detailed insights.",
            default_value="Analyze the forecast data and provide insights about trends, seasonality, and recommendations for planning."
        ),
        SkillParameter(
            name="forecast_viz_layout",
            parameter_type="visualization",
            description="Forecast Visualization Layout",
            default_value=None
        )
    ]
)
def forecast_analysis(parameters: SkillInput) -> SkillOutput:
    """
    Forecast Analysis skill

    Generates intelligent forecasts using multi-model selection and automatic optimization.
    """
    return run_forecast_analysis(parameters)

def run_forecast_analysis(parameters: SkillInput) -> SkillOutput:
    """
    Main forecast analysis logic
    """
    try:
        print(f"DEBUG: Starting forecast analysis")
        print(f"DEBUG: Raw parameters.arguments: {parameters.arguments}")

        # Extract parameters
        metric = parameters.arguments.get('metric')
        forecast_steps = parameters.arguments.get('forecast_steps', 6)
        start_date = parameters.arguments.get('start_date')
        other_filters = parameters.arguments.get('other_filters', [])
        confidence_level = parameters.arguments.get('confidence_level', 0.95)

        print(f"DEBUG: Extracted parameters:")
        print(f"  - metric: {metric} (type: {type(metric)})")
        print(f"  - forecast_steps: {forecast_steps} (type: {type(forecast_steps)})")
        print(f"  - start_date: {start_date} (type: {type(start_date)})")
        print(f"  - other_filters: {other_filters} (type: {type(other_filters)})")
        print(f"  - confidence_level: {confidence_level} (type: {type(confidence_level)})")

        # Convert string parameters to proper types if needed
        if isinstance(forecast_steps, str):
            forecast_steps = int(forecast_steps)
            print(f"DEBUG: Converted forecast_steps to int: {forecast_steps}")

        if isinstance(confidence_level, str):
            confidence_level = float(confidence_level)
            print(f"DEBUG: Converted confidence_level to float: {confidence_level}")

        # Validate inputs
        print(f"DEBUG: Validating forecast_steps: {forecast_steps}")
        if forecast_steps < 1 or forecast_steps > 36:
            print(f"DEBUG: Validation failed - forecast_steps out of range")
            return SkillOutput(
                final_prompt="Invalid forecast steps. Please specify between 1 and 36 months.",
                warnings=["Forecast steps must be between 1 and 36 months"]
            )

        print(f"DEBUG: Calling fetch_data with metric={metric}, start_date={start_date}")

        # Get data from AnswerRocket
        data_df = fetch_data(metric, start_date, other_filters)

        print(f"DEBUG: fetch_data returned, data_df type: {type(data_df)}")
        print(f"DEBUG: data_df is None: {data_df is None}")
        if data_df is not None:
            print(f"DEBUG: data_df.empty: {data_df.empty if hasattr(data_df, 'empty') else 'No empty attribute'}")
            print(f"DEBUG: data_df shape: {data_df.shape if hasattr(data_df, 'shape') else 'No shape attribute'}")

        if data_df is None or data_df.empty:
            return SkillOutput(
                final_prompt="No data available for the specified metric and time range.",
                warnings=["Unable to retrieve data"]
            )

        # Check minimum data requirements
        if len(data_df) < 12:
            return SkillOutput(
                final_prompt=f"Insufficient historical data. Need at least 12 data points but only have {len(data_df)}.",
                warnings=["Minimum 12 historical data points required for forecasting"]
            )

        # Analyze historical patterns
        patterns = analyze_patterns(data_df)

        # Run multiple models
        model_results = run_models(data_df, forecast_steps, confidence_level)

        if not model_results:
            return SkillOutput(
                final_prompt="Unable to generate forecast. All models failed to converge.",
                warnings=["Model fitting failed"]
            )

        # Select best model
        best_model, best_results = select_best_model(model_results)

        # Prepare output data
        output_df = prepare_output(data_df, best_results, best_model, patterns, model_results)

        # Generate prompt for LLM
        prompt = generate_prompt(
            metric=metric,
            forecast_steps=forecast_steps,
            best_model=best_model,
            patterns=patterns,
            model_results=model_results,
            forecast_stats=calculate_forecast_stats(best_results)
        )

        return SkillOutput(
            final_prompt=prompt
        )

    except Exception as e:
        # Don't throw exceptions - return user-friendly error
        print(f"DEBUG: EXCEPTION OCCURRED: {str(e)}")
        print(f"DEBUG: Exception type: {type(e)}")
        import traceback
        print(f"DEBUG: Full traceback:\n{traceback.format_exc()}")
        return SkillOutput(
            final_prompt=f"An error occurred while generating the forecast. Please check your data and try again. Error: {str(e)}",
            warnings=[f"Error: {str(e)}"]
        )

def fetch_data(metric, start_date, other_filters):
    """
    Fetch data using SQL query
    """
    print(f"DEBUG: fetch_data called with metric={metric}, start_date={start_date}, filters={other_filters}")

    # Build SQL query to get time series data for forecasting
    sql_query = f"""
    SELECT
        max_time_month,
        SUM({metric}) as {metric}
    FROM pasta_2025
    WHERE 1=1
    """

    # Add date filter if provided
    if start_date:
        sql_query += f" AND max_time_month >= '{start_date}'"
        print(f"DEBUG: Added date filter: {start_date}")

    # Add other filters
    if other_filters:
        for filter_item in other_filters:
            if isinstance(filter_item, dict):
                for key, value in filter_item.items():
                    if isinstance(value, list):
                        values_str = "', '".join(str(v) for v in value)
                        sql_query += f" AND {key} IN ('{values_str}')"
                    else:
                        sql_query += f" AND {key} = '{value}'"
                    print(f"DEBUG: Added filter: {key} = {value}")

    sql_query += f"""
    GROUP BY max_time_month
    ORDER BY max_time_month
    """

    print(f"DEBUG: Executing SQL query:\n{sql_query}")

    try:
        # Execute SQL query using context
        print(f"DEBUG: About to execute SQL on context")
        print(f"DEBUG: Context type: {type(context)}")

        if hasattr(context, 'sql'):
            result = context.sql(sql_query)
            print(f"DEBUG: SQL executed using context.sql()")
        elif hasattr(context, 'execute_sql'):
            result = context.execute_sql(sql_query)
            print(f"DEBUG: SQL executed using context.execute_sql()")
        else:
            print(f"DEBUG: Context methods available: {[m for m in dir(context) if not m.startswith('_')]}")
            return None

        print(f"DEBUG: SQL result type: {type(result)}")

        if result is not None:
            raw_df = result
            print(f"DEBUG: Got result, shape: {raw_df.shape if hasattr(raw_df, 'shape') else 'No shape'}")
        else:
            print(f"DEBUG: SQL returned None")
            return None

        if raw_df is not None and not raw_df.empty:
            print(f"DEBUG: Raw data columns: {list(raw_df.columns)}")
            print(f"DEBUG: Raw data sample:\n{raw_df.head()}")

            # Standardize column names
            if 'max_time_month' in raw_df.columns:
                raw_df = raw_df.rename(columns={'max_time_month': 'period'})
                print(f"DEBUG: Renamed max_time_month to period")

            if metric in raw_df.columns:
                raw_df = raw_df.rename(columns={metric: 'value'})
                print(f"DEBUG: Renamed {metric} to value")

            print(f"DEBUG: Final columns: {list(raw_df.columns)}")
            print(f"DEBUG: Final shape: {raw_df.shape}")
        else:
            print(f"DEBUG: No data returned from SQL query")

        return raw_df

    except Exception as e:
        print(f"DEBUG: SQL execution failed: {str(e)}")
        return None

def analyze_patterns(df):
    """
    Analyze historical data patterns
    """
    from scipy import stats

    values = df['value'].values
    x = np.arange(len(values))

    # Trend analysis
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, values)

    # Volatility
    returns = pd.Series(values).pct_change().dropna()
    volatility = np.std(returns)

    # Seasonality (simple check)
    seasonal_strength = 0
    if len(values) >= 24:
        monthly_avgs = [np.mean(values[i::12]) for i in range(min(12, len(values)))]
        seasonal_strength = np.std(monthly_avgs) / np.mean(monthly_avgs) if np.mean(monthly_avgs) > 0 else 0

    return {
        'trend_slope': slope,
        'trend_r2': r_value ** 2,
        'trend_direction': 'increasing' if slope > 0 else 'decreasing',
        'volatility': volatility,
        'volatility_level': 'high' if volatility > 0.2 else 'medium' if volatility > 0.1 else 'low',
        'has_seasonality': seasonal_strength > 0.1,
        'data_points': len(values)
    }

def run_models(df, periods, confidence_level):
    """
    Run multiple forecasting models
    """
    from sklearn.linear_model import LinearRegression
    from sklearn.metrics import mean_absolute_error, mean_squared_error

    # Prepare data
    df = df.copy()
    df['period_num'] = range(len(df))

    # Split for validation
    train_size = int(len(df) * 0.8)
    train = df[:train_size]
    validate = df[train_size:]

    models = {}

    # Linear Model
    try:
        X_train = train[['period_num']]
        y_train = train['value']
        X_val = validate[['period_num']]
        y_val = validate['value']

        model = LinearRegression()
        model.fit(X_train, y_train)
        val_pred = model.predict(X_val)

        # Calculate metrics
        mae = mean_absolute_error(y_val, val_pred)
        mape = np.mean(np.abs((y_val - val_pred) / y_val)) * 100

        # Generate full forecast
        future_periods = np.arange(len(df), len(df) + periods).reshape(-1, 1)
        forecast = model.predict(future_periods)

        # Simple confidence intervals
        residuals = y_train - model.predict(X_train)
        std_error = np.std(residuals)
        z_score = 1.96 if confidence_level == 0.95 else 2.58

        models['linear'] = {
            'forecast': forecast,
            'lower_bound': forecast - z_score * std_error,
            'upper_bound': forecast + z_score * std_error,
            'mae': mae,
            'mape': mape,
            'score': mae  # Use MAE as primary score
        }
    except:
        pass

    # Moving Average Model
    try:
        window = min(3, len(train) // 4)
        ma_forecast = []
        recent_values = list(train['value'].values[-window:])

        for _ in range(len(validate)):
            pred = np.mean(recent_values)
            ma_forecast.append(pred)
            recent_values.pop(0)
            recent_values.append(pred)

        mae = mean_absolute_error(validate['value'], ma_forecast)
        mape = np.mean(np.abs((validate['value'] - ma_forecast) / validate['value'])) * 100

        # Full forecast
        recent_values = list(df['value'].values[-window:])
        full_forecast = []
        for _ in range(periods):
            pred = np.mean(recent_values)
            full_forecast.append(pred)
            recent_values.pop(0)
            recent_values.append(pred)

        models['moving_average'] = {
            'forecast': np.array(full_forecast),
            'lower_bound': np.array(full_forecast) * 0.9,  # Simple bounds
            'upper_bound': np.array(full_forecast) * 1.1,
            'mae': mae,
            'mape': mape,
            'score': mae
        }
    except:
        pass

    # Add more models as needed (exponential smoothing, ARIMA, etc.)

    return models

def select_best_model(model_results):
    """
    Select the best performing model
    """
    best_model = None
    best_score = float('inf')

    for model_name, results in model_results.items():
        if results['score'] < best_score:
            best_score = results['score']
            best_model = model_name

    return best_model, model_results[best_model]

def prepare_output(historical_df, forecast_results, model_name, patterns, all_models):
    """
    Prepare output DataFrame
    """
    # Historical data
    hist_df = historical_df.copy()
    hist_df['type'] = 'historical'
    hist_df['forecast'] = np.nan
    hist_df['lower_bound'] = np.nan
    hist_df['upper_bound'] = np.nan
    hist_df.rename(columns={'value': 'actual'}, inplace=True)

    # Forecast data
    forecast_periods = pd.date_range(
        start=hist_df['period'].iloc[-1] + pd.DateOffset(months=1),
        periods=len(forecast_results['forecast']),
        freq='M'
    )

    forecast_df = pd.DataFrame({
        'period': forecast_periods,
        'type': 'forecast',
        'actual': np.nan,
        'forecast': forecast_results['forecast'],
        'lower_bound': forecast_results['lower_bound'],
        'upper_bound': forecast_results['upper_bound']
    })

    # Combine
    output_df = pd.concat([hist_df, forecast_df], ignore_index=True)

    # Add metadata
    output_df['model_used'] = model_name
    output_df['trend_direction'] = patterns['trend_direction']

    return output_df

def calculate_forecast_stats(results):
    """
    Calculate summary statistics for the forecast
    """
    forecast = results['forecast']
    return {
        'total': np.sum(forecast),
        'average': np.mean(forecast),
        'min': np.min(forecast),
        'max': np.max(forecast),
        'growth': ((forecast[-1] - forecast[0]) / forecast[0] * 100) if forecast[0] != 0 else 0
    }

def generate_prompt(metric, forecast_steps, best_model, patterns, model_results, forecast_stats):
    """
    Generate prompt for LLM interpretation
    """
    prompt = f"""
    Analyze this forecast for {metric}:

    FORECAST SUMMARY:
    - Forecast steps: {forecast_steps} months
    - Model selected: {best_model}
    - Total forecasted: {forecast_stats['total']:,.0f}
    - Average per period: {forecast_stats['average']:,.0f}
    - Growth: {forecast_stats['growth']:.1f}%

    HISTORICAL PATTERNS:
    - Trend: {patterns['trend_direction']} (R²={patterns['trend_r2']:.3f})
    - Volatility: {patterns['volatility_level']}
    - Seasonality: {'Yes' if patterns['has_seasonality'] else 'No'}
    - Data points used: {patterns['data_points']}

    MODEL COMPARISON:
    """

    for model_name, results in model_results.items():
        selected = " (SELECTED)" if model_name == best_model else ""
        prompt += f"\n    - {model_name}: MAE={results['mae']:.0f}, MAPE={results['mape']:.1f}%{selected}"

    prompt += """

    Please provide insights about:
    1. Why this model was most appropriate
    2. Key trends and what to expect
    3. Confidence level and risks
    4. Recommendations for planning
    """

    return prompt


if __name__ == '__main__':
    skill_input: SkillInput = forecast_analysis.create_input(arguments={
        'metric': "volume",
        'forecast_steps': 6,
        'start_date': "2022-01-01",
        'other_filters': [{"dim": "manufacturer", "op": "=", "val": ["barilla"]}]
    })