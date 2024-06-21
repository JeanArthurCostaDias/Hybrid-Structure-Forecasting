# -*- coding: utf-8 -*-
"""main.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1oIF1pf73W7f5H-ZEwvL2SNFr10zmq5hm
"""

import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score, mean_absolute_percentage_error
from statsmodels.tsa.seasonal import STL
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from pmdarima.arima import AutoARIMA
import matplotlib.pyplot as plt
import statsmodels.api as sm
from tsai.all import *
from fastai.vision.all import *
from fastai.text.all import *
from fastai.collab import *
from fastai.tabular.all import *
import optuna
import seaborn as sns
from scipy.stats import shapiro, kstest
from statsmodels.stats.diagnostic import het_breuschpagan
from statsmodels.stats.stattools import durbin_watson
from sfrancia import shapiroFrancia

class optuna_optimize:
    def __init__(self,arch,X,y,splits,epochs):
        self.arch = arch
        self.X = X
        self.y = y
        self.splits = splits
        self.epochs = epochs

    def optuna_objective(self,trial):
        hidden_size = trial.suggest_int('hidden_size', 16, 200)
        n_layers = trial.suggest_int('n_layers', 1, 7)
        rnn_dropout = trial.suggest_float('rnn_dropout', 0, 0.8)
        bidirectional = trial.suggest_categorical('bidirectional', [True, False])
        fc_dropout = trial.suggest_float('fc_dropout', 0, 0.8)
        learning_rate_model = trial.suggest_float('learning_rate_model', 1e-5, 1e-1,log=True)

        arch_config ={
            'hidden_size': hidden_size,
            'n_layers': n_layers,
            'rnn_dropout': rnn_dropout,
            'bidirectional': bidirectional,
            'fc_dropout': fc_dropout
        }
        tfms = [None, TSForecasting()]
        learn = TSForecaster(self.X, self.y, splits=self.splits, path='models', tfms=tfms,
                            batch_tfms=TSStandardize(),
                            arch=self.arch, arch_config=arch_config, metrics=[rmse],
                            cbs=[
                                ReduceLROnPlateau(patience=3)
                            ],seed=1)
        
        with ContextManagers([learn.no_bar(),learn.no_logging()]):
            learn.fit_one_cycle(self.epochs, lr_max=learning_rate_model)
            raw_preds, target, _ = learn.get_X_preds(self.X[self.splits[1]], self.y[self.splits[1]])
            intermediate_value = mean_squared_error(y_true=target, y_pred=raw_preds, squared=False)
        
        return intermediate_value



def forecast_arima(series, new_data, seasonal=False, m=1, arima_model=None,
                    start_p=4, start_q=0, d=None, max_p=10, max_q=10, max_d=3, max_order=None,
                    start_P=1, start_Q=1, D=None, max_P=8, max_Q=8, max_D=1):
    
    if not arima_model:
        arima_model = AutoARIMA(start_p=start_p, d=d, start_q=start_q, max_p=max_p, max_d=max_d,
                                max_q=max_q, max_order=max_order, start_P=start_P, D=D, start_Q=start_Q,
                                max_P=max_P, max_D=max_D, max_Q=max_Q, seasonal=seasonal, m=m,
                                trace=True, error_action='ignore', suppress_warnings=True,
                                stepwise=True, information_criterion='aic', scoring='mse',
                                with_intercept='auto')
        
    arima_model = arima_model.fit(y=series)
    lista_previsoes = []
    for j in range(new_data.shape[0]):
        janela_8_dias = new_data[j, 0]
        previsao = arima_model.predict(n_periods=8)
        lista_previsoes.append(previsao)
        arima_model = arima_model.update(janela_8_dias)

    forecast = np.array(lista_previsoes)
    return arima_model, forecast

def forecast_exponential_smoothing(series, new_data, trend='add', seasonal='add', seasonal_periods=7,
                                    initialization_method='heuristic', use_boxcox=False):
    model = ExponentialSmoothing(series, trend=trend, seasonal=seasonal, seasonal_periods=seasonal_periods,
                                    initialization_method=initialization_method, use_boxcox=use_boxcox)
    model_fit = model.fit()

    lista_previsoes = []
    for j in range(new_data.shape[0]):
        previsao = model_fit.forecast(steps=8)
        lista_previsoes.append(previsao)
        series = np.concatenate([series, new_data[j, 0]])
        model = ExponentialSmoothing(series, trend=trend, seasonal=seasonal, seasonal_periods=seasonal_periods,
                                        initialization_method=initialization_method)
        model_fit = model.fit()

    forecast = np.array(lista_previsoes)
    return model_fit, forecast

def forecast_ann(X, y,splits,model = LSTMPlus, epochs=100,arch_config={},btfms=TSStandardize(),loss_func=nn.MSELoss(),cbs=[],lr = None):
    learn = TSForecaster(X, y,splits=splits, arch=model, metrics=[mae, rmse],arch_config=arch_config, batch_tfms=btfms, tfms=[None, [TSForecasting()]], loss_func=loss_func) # type: ignore
    with ContextManagers([learn.no_logging(), learn.no_bar()]):
        if not lr:
            lr = learn.lr_find() # Achar o melhor learning rate pro modelo, método da biblioteca fastai
            learn.fit_one_cycle(epochs, lr_max=lr.valley, cbs=cbs) # Treinar o modelo
        else:
            learn.fit_one_cycle(epochs, lr_max=lr, cbs=cbs)
        print(f'Métricas de Treinamento para {model}')
        display(pd.Series(learn.recorder.values[-1], index=learn.recorder.metric_names[1:5]))
        raw_preds, target, _ = learn.get_X_preds(X[splits[2]],y[splits[2]])
        return raw_preds,target



def decompose_series(series):
    decomposed = STL(series).fit()
    trend = decomposed.trend
    seasonal = decomposed.seasonal
    resid = decomposed.resid
    decomposed.plot()
    return trend, seasonal, resid


def load_and_prepare_data(filepath):
    peru = pd.read_csv(filepath, index_col='index').rename(columns={'GPP': 'peru'})
    peru.index = pd.to_datetime(peru.index)
    peru = peru.resample('D').mean()
    return peru

def residual_summary(forecast, target,dt_index):
    preds_residuals = forecast - target
    residuos = pd.Series(data=preds_residuals, index=dt_index)
    display(residuos)
    print(residuos.describe())

    # Valores ajustados fictícios para ilustrar (geralmente não disponíveis apenas com resíduos)
    valores_ajustados = forecast

    # Configuração do layout dos subplots
    fig = plt.figure(figsize=(14, 15))
    gs = fig.add_gridspec(3, 2)

    # Gráfico dos resíduos versus valores ajustados (valores fictícios)
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.scatter(valores_ajustados, preds_residuals)
    ax1.axhline(0, color='red', linestyle='--')
    ax1.set_title('Resíduos vs Valores Ajustados')

    # Q-Q plot dos resíduos para verificar normalidade
    ax2 = fig.add_subplot(gs[0, 1])
    sm.qqplot(preds_residuals, line='s', ax=ax2)
    ax2.set_title('Q-Q Plot dos Resíduos')

    # Histograma dos resíduos
    ax3 = fig.add_subplot(gs[1, 0])
    sns.histplot(x=preds_residuals, kde=True, ax=ax3)
    ax3.set_title('Histograma com KDE dos Resíduos')

    # Gráfico de autocorrelação dos resíduos
    ax4 = fig.add_subplot(gs[1, 1])
    sm.graphics.tsa.plot_acf(preds_residuals, ax=ax4)
    ax4.set_title('Autocorrelação dos Resíduos')

    # Resíduos vs. Tempo (ocupando a segunda linha inteira)
    ax5 = fig.add_subplot(gs[2, :])
    ax5.plot(preds_residuals)
    ax5.axhline(0, color='red', linestyle='--')
    ax5.set_title('Resíduos ao longo do Tempo')

    plt.tight_layout()
    plt.show()

    # Testes Estatísticos e Interpretações
    shapiro_pvalue = shapiro(preds_residuals)[1]
    kstest_pvalue = kstest(preds_residuals, 'norm')[1]
    durbin_watson_stat = durbin_watson(preds_residuals)
    
    print("Shapiro-Wilk Test p-value:", shapiro_pvalue)
    if shapiro_pvalue > 0.05:
        print("Interpretação: Não podemos rejeitar a hipótese nula de que os resíduos seguem uma distribuição normal (p > 0.05).")
    else:
        print("Interpretação: Rejeitamos a hipótese nula de que os resíduos seguem uma distribuição normal (p <= 0.05).")
        
    print("Kolmogorov-Smirnov Test p-value:", kstest_pvalue)
    if kstest_pvalue > 0.05:
        print("Interpretação: Não podemos rejeitar a hipótese nula de que os resíduos seguem uma distribuição normal (p > 0.05).")
    else:
        print("Interpretação: Rejeitamos a hipótese nula de que os resíduos seguem uma distribuição normal (p <= 0.05).")

    shapiro_francia_pvalue = shapiroFrancia(preds_residuals)['p-value']
    print("Shapiro-Francia Test p-value:", shapiro_francia_pvalue)
    if shapiro_francia_pvalue > 0.05:
        print("Interpretação: Não podemos rejeitar a hipótese nula de que os resíduos seguem uma distribuição normal (p > 0.05).")
    else:
        print("Interpretação: Rejeitamos a hipótese nula de que os resíduos seguem uma distribuição normal (p <= 0.05).")

        
    print("Durbin-Watson Statistic:", durbin_watson_stat)
    if durbin_watson_stat < 1.5 or durbin_watson_stat > 2.5:
        print("Interpretação: Possível autocorrelação nos resíduos (Durbin-Watson fora do intervalo 1.5-2.5).")
    else:
        print("Interpretação: Não há evidência de autocorrelação nos resíduos (Durbin-Watson dentro do intervalo 1.5-2.5).")
    
    # Teste de Heterocedasticidade
    model = sm.OLS(preds_residuals, sm.add_constant(valores_ajustados)).fit()
    _, pval, _, f_pval = het_breuschpagan(model.resid, model.model.exog)
    print('Breusch-Pagan Test p-value:', pval)
    if pval > 0.05:
        print("Interpretação: Não podemos rejeitar a hipótese nula de homocedasticidade (variância constante dos resíduos) (p > 0.05).")
    else:
        print("Interpretação: Rejeitamos a hipótese nula de homocedasticidade (variância constante dos resíduos) (p <= 0.05).")

def Default_LSTM(peru):
    peru_x,peru_y = SlidingWindow(window_len=8,horizon=8,stride=None)(peru['peru'].values)
    splits = TSSplitter(valid_size=0.15,test_size=0.15)(peru_y)
    optuna_opt = optuna_optimize(LSTMPlus,peru_x,peru_y,splits)

    study = run_optuna_study(optuna_opt.optuna_objective,sampler= optuna.samplers.TPESampler(n_startup_trials=500,seed=1),n_trials=1000,gc_after_trial=True,direction="minimize",show_plots=False)
    print(f"O Melhor modelo foi o de número {study.best_trial.number}")
    print("Best hyperparameters: ", study.best_trial.params)

    peru_forecast, target_peru = forecast_ann(peru_x, peru_y, splits, model=LSTMPlus, epochs=100,
                                                     arch_config={key: value for key, value in list(study.best_trial.params.items())[:-1]},
                                                     btfms=TSStandardize(),loss_func=HuberLoss('mean'),cbs=[ReduceLROnPlateau(patience=3)],
                                                     lr=study.best_trial.params['learning_rate_model'])

    print(f"RMSE: {mean_squared_error(target_peru.flatten(), peru_forecast.flatten(), squared=False)}")
    print(f"MAE: {mean_absolute_error(target_peru.flatten(), peru_forecast.flatten())}")
    print(f"R²: {r2_score(target_peru.flatten(), peru_forecast.flatten())}")
    print(f"MAPE: {mean_absolute_percentage_error(target_peru.flatten(), peru_forecast.flatten())}")
    print(f"Correlação Linear: {np.corrcoef(target_peru.flatten(), peru_forecast.flatten())[0, 1]}")

    plt.figure(figsize=(20, 5))
    plt.plot(target_peru.flatten())
    plt.plot(peru_forecast.flatten())
    plt.show()

    residual_summary(peru_forecast.flatten(), target_peru.flatten(), peru['peru'].loc[peru['peru'].isin(peru_y[splits[2]].flatten())].index)



def STL_ARIMA_ES_LSTM(peru):

    trend, seasonal, resid = decompose_series(peru)

    resid_x,resid_y = SlidingWindow(window_len=8,horizon=8,stride=None)(resid.values)
    splits_testando = TSSplitter(valid_size=0.15,test_size=0.15)(resid_y)

    # optuna_opt = optuna_optimize(LSTMPlus,resid_x,resid_y,splits_testando,epochs=50)
    # study = run_optuna_study(optuna_opt.optuna_objective,sampler= optuna.samplers.TPESampler(n_startup_trials=500,seed=1),n_trials=1000,gc_after_trial=True,direction="minimize",show_plots=False)
    # print(f"O Melhor modelo foi o de número {study.best_trial.number}")
    # print("Best hyperparameters: ", study.best_trial.params)


    residual_forecast,target_residual = forecast_ann(resid_x, resid_y,splits_testando,model=LSTMPlus, epochs=50,
                                                     arch_config={'hidden_size': 135, 'n_layers': 2, 'rnn_dropout': 0.6193926562216368, 'bidirectional': True, 'fc_dropout': 0.209474313213079},
                                                     btfms=TSStandardize(),loss_func=HuberLoss('mean'),cbs=[ReduceLROnPlateau(patience=3)],
                                                     lr=0.0008327152231865279
                                                     )

    train_values = np.concatenate([resid_x[splits_testando[0]].flatten(),resid_x[splits_testando[1]].flatten()])
    train_index = resid.loc[resid.isin(train_values)].index
    test_index = resid.loc[resid.isin(resid_x[splits_testando[2]].flatten())].index

    train_trend = trend.loc[train_index]
    test_trend = trend.loc[test_index]

    arima_model, trend_forecast = forecast_arima(series=train_trend,new_data=test_trend.values.reshape(-1,1,8))

    train_seasonal = seasonal.loc[train_index]
    test_seasonal = seasonal.loc[test_index]
    es_model, seasonal_forecast = forecast_exponential_smoothing(series=train_seasonal,new_data=test_seasonal.values.reshape(-1,1,8),trend=None,seasonal_periods=7)

    final_pred = residual_forecast.flatten() + seasonal_forecast.flatten() + trend_forecast.flatten()
    real_values = target_residual.numpy().flatten() + test_trend + seasonal[test_trend.index]
    index = real_values.index
    real_values = real_values.values
    final_pred = final_pred.numpy()

    print(f"RMSE: {mean_squared_error(real_values, final_pred, squared=False)}")
    print(f"MAE: {mean_absolute_error(real_values, final_pred)}")
    print(f"R²: {r2_score(real_values, final_pred)}")
    print(f"MAPE: {mean_absolute_percentage_error(real_values, final_pred)}")
    print(f"Correlação Linear: {np.corrcoef(real_values, final_pred)[0, 1]}")

    plt.figure(figsize=(20, 5))
    plt.plot(index, real_values)
    plt.plot(index, final_pred)
    plt.show()

    residual_summary(final_pred, real_values, resid.loc[resid.isin(resid_x[splits_testando[2]].flatten())].index)


def main():
    filepath = 'peru.csv'
    peru = load_and_prepare_data(filepath)
    print('====================================================================================================')
    print('STL + ARIMA + ES + LSTM')
    STL_ARIMA_ES_LSTM(peru=peru)
    print('====================================================================================================')
    print('Default LSTM')
    Default_LSTM(peru=peru)

main()
