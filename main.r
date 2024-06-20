chooseCRANmirror()  # Escolha o número correspondente ao espelho mais próximo de você

install.packages('forecast', dependencies = TRUE)
library(forecast)

df <- read.csv("peru.csv", header=TRUE, sep=",",index_col='index', parse_dates=TRUE, infer_datetime_format=TRUE)
time_series <- ts(df$peru, frequency = 1)
cleaned_series <- tsclean(time_series)
print(head(cleaned_series))