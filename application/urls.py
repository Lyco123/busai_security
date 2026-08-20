# @File           : urls.py
# @IDE            : PyCharm
# @desc           : 路由文件


from apps.vadmin.analysis.views import app as vadmin_analysis_app



# 引入应用中的路由
urlpatterns = [
    {"ApiRouter": vadmin_analysis_app, "prefix": "/vadmin/analysis", "tags": ["数据分析管理"]},
]
