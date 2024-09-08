# 租房信息爬取

目前采集的是豆瓣租房小组的帖子

## 执行

1. 准备工作

```text
a. 修改config/config.py文件的配置，添加变量
* https://www.douban.com/group/sweethome/，其中豆瓣的组ID为"sweethome"
* {city}是填写你需要采集的城市

eg：
# put 豆瓣的组ID here
{city}_groups = [
    "beijingzufang",
    "zhufang",
    "sweethome",
    "opking",
]

# set yourself location keywords
{city}_locations = [
    "学院路地铁口",
]

# set yourself house type
{city}_house = ["一室"]



b. 修改app.py, main中传递的是需要采集的city
if __name__ == '__main__':
    douban.main("beijing")
    # douban.main("shanghai")

```

2. 启动采集

- 如果使用docker启动

```bash
# 构建镜像
./debug_build.sh 

(重构镜像时可使用：./debug_build.sh --build)

# 容器内执行
./start.sh
```

```bash
./debug_build.sh 

(重构镜像时可使用：./debug_build.sh --build)
```

- 直接启动
  
```bash
# 安装依赖
pip install -r /app/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 开始采集
./start.sh
```

3. 采集后的文件保存在了 `/tmp` 目录下
