import requests                #请求
from bs4 import BeautifulSoup  #用了里面的lxml解析器 
from fake_useragent import UserAgent   #生成不同的浏览器标识（UA ）  
import xlwt                    #写入Excel文件
from datetime import datetime  #获取时间
import multiprocessing         #多进程
from retrying import retry     #让函数重复执行
import json                    #解析json格式
import time                    #设置延时

'''
目的：将多个网站的bike数据用一个程序爬出来
    
 共五个网站：
        www.kupujemprodajem.com   无反爬  
        www.verkkokauppa.com/   ajax
        www.emag.bg             不要爬太快，会出验证码
        www.ebay.com           

    2.面向对象，每个网站是一个类。

    3.做了个实验。
        爬 kupujemprodajem时，
            - 不用多进程/多线程，10秒爬一页；
            - 多线程，爬100页 --> 2分钟
            - 多进程，爬100页 --> 1分钟
步骤
    1.构造四个类，每个类定义四个实例方法 
            get_response(获取本页响应的源代码),
            analysis(解析本页的源代码，把数据放到相应队列中),
            add_sheet(把队列中的内容取出来，放入sheet中)
            main(与run()对接，创建进程池来实现多进程)
    2.定义run()方法，创建对象运行各自的main(),设计人与程序的简单交互
    3.优化，捕获异常，重构代码

'''

# 不要保持连接状态
s = requests.session()
s.keep_alive = False

ex=xlwt.Workbook(encoding="utf-8",style_compression=0)

def xstr(s):
    '''都转化为字符串'''
    if s is None:
        return ''
    return str(s)


class KUPUJEMPRODAJEM():
    def __init__(self):
        self.query_name=''
        self.name_q=multiprocessing.Manager().Queue()
        self.price_q=multiprocessing.Manager().Queue()
        self.url_q=multiprocessing.Manager().Queue()
        self.description_q=multiprocessing.Manager().Queue()
        self.time_q=multiprocessing.Manager().Queue()

    @retry(stop_max_attempt_number=3)  #让被装饰的函数反复执行三次，三次全部报错才会报错  
    def get_response(self,page):
        '''获取当前页面的源代码'''
        headers={'UserAgent':UserAgent().firefox,
        }
        session=requests.session()
        url="https://www.kupujemprodajem.com/search.php?action=list&data[action]=list&data[submit][search]=Traži&data[dummy]=name&data[keywords]="+self.query_name+"&data[list_type]=search&data[page]="+str(page)
        r=session.get(url,headers=headers)
        return r.text

    def analysis(self,page):  
        '''解析当前页面响应，并把数据存到队列中'''          
        soup=BeautifulSoup(self.get_response(page),'lxml')
        for i in range(len(soup.find_all("a",class_='adName'))):
            self.name_q.put(soup.find_all("a",class_='adName')[i].string.strip())
            self.price_q.put(soup.find_all("span",class_='adPrice')[i].string.strip())
            self.url_q.put('https://www.kupujemprodajem.com'+soup.find_all("a",class_="adName")[i].get("href"))
            self.description_q.put(soup.find_all("div",class_="adDescription descriptionHeight")[i].string.strip())
            self.time_q.put(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        print(datetime.now().strftime('%Y-%m-%d %H:%M:%S')+" : "+"第"+str(page)+"页爬取成功")

    def get_max_page(self):
        '''顾名思义，获取最大页数'''
        url='https://www.kupujemprodajem.com/search.php?action=list&submit[search]=Traži&dummy=name&data[keywords]='+self.query_name
        headers={'UserAgent':UserAgent().random}
        try:
            r=requests.get(url,headers=headers)
            max_page=BeautifulSoup(r.text,'lxml').find("ul",class_="pagesList").find_all("li")[-2].a.string
        except Exception as e:
            print("有异常发生：",e)
            return 1
        else:
            return int(max_page)

    def add_sheet(self):
        #初始化excel表格
        kupu_sheet=ex.add_sheet("kupujemprodajem",cell_overwrite_ok=True)
        e_list=["时间","名字","价格","数据源","详情"]
        for i in range(len(e_list)):
            kupu_sheet.write(0,i,e_list[i])
        #将数据添加到Excel 中
        for i in range(self.time_q.qsize()): #qsize()获取队列长度
            kupu_sheet.write(i+1,0,self.time_q.get())
            kupu_sheet.write(i+1,1,self.name_q.get())
            kupu_sheet.write(i+1,2,self.price_q.get())
            kupu_sheet.write(i+1,3,self.url_q.get())
            kupu_sheet.write(i+1,4,self.description_q.get())

    def main(self,select):
        '''执行主要逻辑：
        交互，
        创建进程池（获取响应，解析响应），
        保存数据
        '''
        if select==1:
            self.query_name='bike'
            print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'),"正在爬取kupujemprodajem......")
            page_1=self.get_max_page()
            print("最大页数为：",page_1)
            pool=multiprocessing.Pool() 
            pages=range(1,int(page_1)-10)
            pool.map(self.analysis,pages)
            pool.close()
            pool.join()
            print("ok !")
            self.add_sheet()
        else:
            self.query_name=input("请输入商品的英文名字：")
            print("最大页数为：",self.get_max_page())
            page_0=input("请输入你想爬取的起始页数: ")
            page_1=input("请输入你想爬取的末尾页数: ")
            print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'),"正在爬取第"+page_0+"页到"+page_1+"页的"+self.query_name+"数据......")
            pool=multiprocessing.Pool() # 智能调用CPU内核。括号里可指定 processes=CPU核数
            pages=range(int(page_0),int(page_1)+1)
            pool.map(self.analysis,pages)
            pool.close()
            pool.join()
            print("OK !!!")
            self.add_sheet()


class EMAG():
    def __init__(self):
        self.query_name=''
        self.name_q=multiprocessing.Manager().Queue()
        self.url_q=multiprocessing.Manager().Queue()
        self.price_q=multiprocessing.Manager().Queue()
        self.time_q=multiprocessing.Manager().Queue()

    @retry(stop_max_attempt_number=3)
    def get_response(self,page):
        time.sleep(0.4)
        headers={'UserAgent':UserAgent().random}
        session=requests.session()
        url='https://www.emag.bg/search/'+self.query_name+'/p'+str(page)
        r=session.get(url,headers=headers)
        if r.status_code == 200:
            print("响应成功")
            return r.text
        else:
            print("获取响应失败",r)

    def analysis(self,page):
        soup=BeautifulSoup(self.get_response(page),'lxml')
        priceList=soup.select('#card_grid .card-body  p.product-new-price') #价格列表。待处理
        for i in range(len(soup.select("h2 a"))):
            self.name_q.put(soup.select('h2 a')[i].string.strip())
            self.url_q.put(soup.select("h2 a")[i].get("href"))
            self.price_q.put(priceList[i].contents[0].string+'.'+priceList[i].contents[1].string+priceList[i].contents[3].string)
            self.time_q.put(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        print(datetime.now().strftime('%Y-%m-%d %H:%M:%S')+" : "+"第"+str(page)+"页爬取成功")

    def get_max_page(self):
        headers={'UserAgent':UserAgent().firefox}
        url='https://www.emag.bg/search/'+self.query_name+'?ref=effective_search'
        try:
            r=requests.get(url,headers=headers)
            max_page=BeautifulSoup(r.text,'lxml').find("ul",id="listing-paginator").find_all("li")[-2].a.string
        except Exception as e:
            print("出现异常：",e)
            return 1
        else:
            return max_page

    def add_sheet(self):
        #初始化excel表格
        em_sheet=ex.add_sheet("emag",cell_overwrite_ok=True)
        e_list=["时间","名字","价格","数据源","详情"]
        for i in range(len(e_list)):
            em_sheet.write(0,i,e_list[i])
        #将数据添加到Excel 中
        for i in range(self.time_q.qsize()): #qsize()获取队列长度
            em_sheet.write(i+1,0,self.time_q.get())
            em_sheet.write(i+1,1,self.name_q.get())
            em_sheet.write(i+1,2,self.price_q.get())
            em_sheet.write(i+1,3,self.url_q.get())
            # sheet.write(i+1,4,self.description_q.get())

    def main(self,select):
        if select==1:
            self.query_name='bike'
            print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'),"正在爬取emag......")
            page_1=self.get_max_page()
            print("最大页数为：",page_1)
            pool=multiprocessing.Pool() 
            pages=range(1,int(page_1)+1)
            pool.map(self.analysis,pages)
            pool.close()
            pool.join()
            print("ok !")
            self.add_sheet()
        else:
            self.query_name=input("请输入商品的英文名字：")
            print("最大页数为：",self.get_max_page())
            page_0=input("请输入你想爬取的起始页数: ")
            page_1=input("请输入你想爬取的末尾页数: ")
            pool=multiprocessing.Pool() 
            pages=range(int(page_0),int(page_1)+1)
            pool.map(self.analysis,pages)
            pool.close()
            pool.join()
            self.add_sheet()
            print("OK !!!!")

class EBAY():
    def __init__(self):
        self.query_name=''
        self.name_q=multiprocessing.Manager().Queue()
        self.url_q=multiprocessing.Manager().Queue()
        self.price_q=multiprocessing.Manager().Queue()
        self.time_q=multiprocessing.Manager().Queue()

    def get_response(self,page):
        url='https://www.ebay.com/sch/i.html?_from=R40&_nkw='+self.query_name+'&_sacat=0&_pgn='+str(page)
        headers={'UserAgent':UserAgent().firefox,
        'Cookie': 'dp1=bu1p/QEBfX0BAX19AQA**6388b0de^pbf/#8000000000e4006000000000000000006388b0eb^bl/CN6388b0de^; nonsession=BAQAAAXQoEGjGAAaAADMABmGnfV4wMzAwMDAAygAgY4iw3mUxNjVlYWU1MTc1MGE3N2RhNDA2ODBjMmZmYzk4ZWJlAMsAAV/GUOYxXoheVW3ESjqyCxTZxv/TkAKbtsM*; ns1=BAQAAAXQoEGjGAAaAANgASmGnfV5jNjl8NjAxXjE2MDU4MDQzNzM1OTleXjFeM3wyfDV8NHw3fDExXl5eNF4zXjEyXjEyXjJeMV4xXjBeMV4wXjFeNjQ0MjQ1OTA3NZij7qJShldxdyhqOwJyxMEZEOZV; s=CgAD4ACBfx4xvZTE2NWVhZTUxNzUwYTc3ZGE0MDY4MGMyZmZjOThlYmUsIAYb; ebay=%5Ejs%3D1%5Esbf%3D%23000000%5E; ak_bmsc=2BD2B44F308F4F9B3BE6EB1001E8A04A0211721D18130000C43AC65F4E38D210~pl72nUwvMBJtw8HYf/HgZx5sGRW5fSYhxsy4RAB1TJGIABA/eJp9gXqFHWtPjN952mpsr3WrBBCEsSN2gyr7ypuBmq4kIHTWBtbzGg66MV2jQZOtv0lK5+3HOHw943nEUqDfRs97JpyUTb/H8RpM67I7xW8hfhwoEFj2+j/WrzHJt/5Hs7Dyi7Nrdnp9qqck3sVlHP6U/PvU5bapQGQKZKWOw/6sOL6+apNQN4ZxlJvBk=; bm_sv=72158C368F79050FD3633ABA4A17D382~NW53aKPVjDrZ5PuNpjf2enuIlJnHlfOYpoJSWi1Zw/UOwwADTIvAEdij4rHD1mMyeiOMXS/hUL5XWd3iCNk9b3enT7NK+k5vDjDcxfYl/27yKkNMUssaLcEJYrpKMtBR6Mi7K82oksP6B+1VmcRCSsAysLKTgXLoZs/Rx//968Y=',
        'Referer': 'https://www.ebay.com/'
        }
        r=requests.get(url,headers=headers)
        if r.status_code ==200:
            return r.text
        else:
            print("响应失败")


    def analysis(self,page):
        soup=BeautifulSoup(self.get_response(page),'lxml')
        for i in range(len(soup.select('h3.s-item__title'))):
            self.name_q.put(xstr(soup.select('h3.s-item__title')[i].contents[-1]))# type(contents[-1])是NavigableString把它转化成String,不然报错：RecursionError: maximum recursion depth exceeded while pickling an object
            self.price_q.put(xstr(soup.select('.s-item__details')[i].div.span.string))
            self.url_q.put(soup.select('.s-item__link')[i].get("href"))
            self.time_q.put(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        print(datetime.now().strftime('%Y-%m-%d %H:%M:%S')+" : "+"第"+str(page)+"页爬取成功")


    def add_sheet(self):
        #初始化excel表格
        eb_sheet=ex.add_sheet("ebay",cell_overwrite_ok=True)
        e_list=["时间","名字","价格","数据源"]
        for i in range(len(e_list)):
            eb_sheet.write(0,i,e_list[i])
        #将数据添加到Excel 中
        for i in range(self.time_q.qsize()): #qsize()获取队列长度
            eb_sheet.write(i+1,0,self.time_q.get())
            eb_sheet.write(i+1,1,self.name_q.get())
            eb_sheet.write(i+1,2,self.price_q.get())
            eb_sheet.write(i+1,3,self.url_q.get())

    def main(self,select):
        if select==1:
            self.query_name='bike'
            print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'),"正在爬取ebay......")
            page_1=140
            print("该网站最多获取10000个数据，最大页数固定为：160")
            pool=multiprocessing.Pool() 
            pages=range(1,140)
            pool.map(self.analysis,pages)
            pool.close()
            pool.join()
            print("ok !")
            self.add_sheet()
        else:
            self.query_name=input("请输入商品的英文名字：")
            print("该网站最多获取10000个数据，最大页数固定为：160")
            page_0=input("请输入你想爬取的起始页数: ")
            page_1=input("请输入你想爬取的末尾页数: ")
            pool=multiprocessing.Pool() 
            pages=range(int(page_0),int(page_1)+1)
            pool.map(self.analysis,pages)
            pool.close()
            pool.join()
            print("OK !!!")
            self.add_sheet()


class VERKKOKAUPPA():
    def __init__(self):
        self.query_name=''
        self.name_q=multiprocessing.Manager().Queue()
        self.url_q=multiprocessing.Manager().Queue()
        self.price_q=multiprocessing.Manager().Queue()
        self.time_q=multiprocessing.Manager().Queue()

    def get_response(self,page):
        headers={'UserAgent':UserAgent().firefox}
        url="https://web-api.service.verkkokauppa.com/search?pageNo="+str(page-1)+"&query="+self.query_name+"&sort=score:desc&rrSessionId=11b2a6da-2588-42d1-83c7-3d363af66aa6&rrRcs=eF5j4cotK8lM4bO0sNQ11DVkKU32MDBMMzAwN07TNU9LMdM1SUo2001KTDbQTTU1TTFNNTE1MzI0BQCLxA42"
        r=requests.get(url,headers=headers)
        return json.loads(r.text)

    def analysis(self,page):
        dict=self.get_response(page)['products']
        for i in range(len(dict)):
            self.name_q.put(dict[i]["name"]["fi"])
            # original_priceL.append(dict[i]["price"]["originalFormatted"])
            self.price_q.put(dict[i]["price"].get("currentFormatted")) #python字典操作。如果key对应的value不存在，则返回default
            self.url_q.put('https://www.verkkokauppa.com/fi/product/'+str(dict[i]["productId"]))
            # short_introduce.append(BeautifulSoup(dict[i]["description"]["fi"],'lxml').p.string)
            # soup=BeautifulSoup(dict[i]["description"]["fi"],'lxml').find_all('li')
            # ss=''
            # for j in soup:
            #     ss+=j.get_text()+'\n'
            # detailes.append(ss)
            self.time_q.put(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        print(datetime.now().strftime('%Y-%m-%d %H:%M:%S')+" : "+"第"+str(page)+"页爬取成功")
        
    def add_sheet(self):
        #初始化excel表格
        ve_sheet=ex.add_sheet("verkkokauppa",cell_overwrite_ok=True)
        e_list=["时间","名字","价格","数据源"]
        for i in range(len(e_list)):
            ve_sheet.write(0,i,e_list[i])
        #将数据添加到Excel 中
        for i in range(self.time_q.qsize()): #qsize()获取队列长度
            ve_sheet.write(i+1,0,self.time_q.get())
            ve_sheet.write(i+1,1,self.name_q.get())
            ve_sheet.write(i+1,2,self.price_q.get())
            ve_sheet.write(i+1,3,self.url_q.get())

    def main(self,select):
        if select==1:
            self.query_name='bike'
            print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'),"正在爬取verkkokauppa......")
            page_1=self.get_response(1)['numPages']
            print("最大页数为：",page_1)
            pool=multiprocessing.Pool() 
            pages=range(1,int(page_1)+1)
            pool.map(self.analysis,pages)
            pool.close()
            pool.join()
            print("ok !")
            self.add_sheet()
        else:
            self.query_name=input("请输入商品的英文名字：")
            print("最大页数为：",self.get_response(1)['numPages'])
            page_0=input("请输入你想爬取的起始页数: ")
            page_1=input("请输入你想爬取的末尾页数: ")
            pool=multiprocessing.Pool() 
            pages=range(int(page_0),int(page_1)+1)
            pool.map(self.analysis,pages)
            pool.close()
            pool.join()
            print("ok  !!")
            self.add_sheet()

class OTTOVERSAND():
    def __init__(self):
        self.query_name=''
        self.name_q=multiprocessing.Manager().Queue()
        self.price_q=multiprocessing.Manager().Queue()
        self.url_q=multiprocessing.Manager().Queue()
        self.time_q=multiprocessing.Manager().Queue()

    def get_response(self,page):
      url = 'https://www.ottoversand.at/api/s'
      headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:82.0) Gecko/20100101 Firefox/82.0'}
      session=requests.session()
      payloadData ={"previousRequest":{"query":"","clientId":"OttoversandAt","count":72,"filters":{},"locale":"de_DE","minAvailCode":2,"order":"relevance","pageNoDisplay":1,"specialArticles":[],"start":0,"version":10},"userAgent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:82.0) Gecko/20100101 Firefox/82.0","personalization":"$$$$web$$","channel":"web","query":self.query_name,"clientId":"OttoversandAt","count":72,"filters":{},"locale":"de_AT","minAvailCode":2,"order":"relevance","pageNoDisplay":page,"specialArticles":[],"start":0,"version":10,"allowTest":'false',"seoFiltered":'false',"doRedirectToCategoryUrl":'false'}
      r=session.post(url,headers=headers,data=json.dumps(payloadData))
      with open('json.txt','w',encoding='utf-8') as f:
        f.write(r.text)
      return json.loads(r.text)
    def analysis(self,page):
        dic=self.get_response(page)['searchresult']["result"]['products']
        for i in range(len(dic)):
            self.name_q.put(dic[i]['name']) #名字
            self.price_q.put(str(dic[i]['variations'][0]['price']['value']).strip())#价格：欧元
            self.url_q.put('https://www.ottoversand.at'+dic[i]['variations'][0]['productUrl'])#链接
            self.time_q.put(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        print(datetime.now().strftime('%Y-%m-%d %H:%M:%S')+" : "+"第"+str(page)+"页爬取成功")

    def get_max_page(self):
        dic=self.get_response(1)['searchresult']
        a=dic['result']['count']
        b=dic['request']['count']
        c=a%b
        if c!=0:
            c=a//b+1
        else:
            c=a//b
        return c
    def add_sheet(self):
        ot_sheet=ex.add_sheet("ottoversand",cell_overwrite_ok=True)
        e_list=["时间","名字","价格","数据源"]
        for i in range(len(e_list)):
            ot_sheet.write(0,i,e_list[i])
        for i in range(self.time_q.qsize()): #qsize()获取队列长度
            ot_sheet.write(i+1,0,self.time_q.get())
            ot_sheet.write(i+1,1,self.name_q.get())
            ot_sheet.write(i+1,2,self.price_q.get())
            ot_sheet.write(i+1,3,self.url_q.get())


    def main(self):
        self.query_name=input("输入搜索名字：")
        print("最大页数为：",self.get_max_page())
        page_0=input("请输入你想爬取的起始页数: ")
        page_1=input("请输入你想爬取的末尾页数: ")
        pool=multiprocessing.Pool() 
        pages=range(int(page_0),int(page_1)+1)
        pool.map(self.analysis,pages)
        pool.close()
        pool.join()
        print("ojbk !!")
        self.add_sheet()


class GJIRAFA50():
    '''
    改变cookies中rel。rel:1  -不显示已出售商品； rel：2   -显示出售商品
    '''
    def __init__(self):
        self.query_name=''
        self.name_q=multiprocessing.Manager().Queue()
        self.price_q=multiprocessing.Manager().Queue()
        self.url_q=multiprocessing.Manager().Queue()
        self.time_q=multiprocessing.Manager().Queue()

    @retry(stop_max_attempt_number=3) #给爷请求三次再报错
    def get_response(self,page):
        url='https://gjirafa50.com/index.php?dispatch=products.search&q='+self.query_name+'&isAjax=1&page='+str(page)+'&limit=48&sort_by=&sort_order=&features_hash=961-1.5-3979.5-EUR'
        headers={'UserAgent':UserAgent().firefox,
        'Cookie': '__zlcmid=10ojWvKDgqdLkI5; __cfduid=d6dbcf6f037b75c5ca6c744f50684d4c91606462111; sid_customer_325d8=bae7d12e604b73eaa4229a83cdaf4c01-1-C; rel=1; c=CN; gjs=ovh.sbg3.ubn.web.03',
        'Host': 'gjirafa50.com',
        'Referer': 'https://gjirafa50.com/?rel=1&q=computer&dispatch=products.search',
        'X-Requested-With': 'XMLHttpRequest'}
        r=requests.get(url,headers=headers)
        return r.text

    def analysis(self,page):
        '''这个网站是Ajax+xml'''
        soup=BeautifulSoup(self.get_response(page),'lxml')
        for i in range(len(soup.find_all("span",class_="ty-price"))):
            self.name_q.put(soup.find_all("a",class_="product-title")[i].string.strip())
            self.price_q.put(soup.find_all("span",class_="ty-price")[i].get_text())
            self.url_q.put(soup.find_all("a",class_="product-title")[i].get("href"))
            self.time_q.put(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        print(datetime.now().strftime('%Y-%m-%d %H:%M:%S')+" : "+"第"+str(page)+"页爬取成功")

    def add_sheet(self):
        sheet=ex.add_sheet("gjirafa50",cell_overwrite_ok=True)
        slist=["时间","名字","价格","数据源"]
        for i in range(len(slist)):
            sheet.write(0,i,slist[i])
        for i in range(self.time_q.qsize()): 
            sheet.write(i+1,0,self.time_q.get())
            sheet.write(i+1,1,self.name_q.get())
            sheet.write(i+1,2,self.price_q.get())
            sheet.write(i+1,3,self.url_q.get())

    def get_max_page(self):
        url='https://gjirafa50.com/?rel=1&q='+self.query_name+'&dispatch=products.search'
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:82.0) Gecko/20100101 Firefox/82.0',
        'Cookie': '__zlcmid=10ojWvKDgqdLkI5; __cfduid=d6dbcf6f037b75c5ca6c744f50684d4c91606462111; sid_customer_325d8=bae7d12e604b73eaa4229a83cdaf4c01-1-C; rel=1; c=CN; gjs=ovh.sbg3.ubn.web.03',
        'Upgrade-Insecure-Requests': '1'}
        r=requests.get(url,headers=headers)
        a=int(BeautifulSoup(r.text,'lxml').find('span',id="products_search_total_found_11").string.split(": ")[1])
        b=48
        if a%b == 0:
            c=a//b
        else:
            c=a//b+1
        return c 

    def main(self):
        self.query_name=input("输入搜索名字：")
        print("最大页数为：",self.get_max_page())
        page_0=input("请输入你想爬取的起始页数: ")
        page_1=input("请输入你想爬取的末尾页数: ")
        pool=multiprocessing.Pool() 
        pages=range(int(page_0),int(page_1)+1)
        pool.map(self.analysis,pages)
        pool.close()
        pool.join()
        print("ojbk !!")
        self.add_sheet()

class LIMUNDO():
    def __init__(self):
        self.query_name=''
        self.name_q=multiprocessing.Manager().Queue()
        self.price_q=multiprocessing.Manager().Queue()
        self.url_q=multiprocessing.Manager().Queue()
        self.time_q=multiprocessing.Manager().Queue()

    def get_response(self,page):
        url='https://www.limundo.com/pretragaLimundo.php?txtPretraga='+self.query_name+'&Okrug=-1&Opstina=-1&sSmer=ASC&iStr='+str(page)
        headers = {'UserAgent':UserAgent().random,'Host':'www.limundo.com'}
        r=requests.get(url,headers=headers)
        return r.text

    def analysis(self,page):
        soup=BeautifulSoup(self.get_response(page),'lxml')
        for i in range(len(soup.select("li div h2 a"))):
            self.name_q.put(soup.select("li div h2 a")[i].string.strip())
            self.price_q.put(soup.find_all('p',class_='orange_txt')[i].contents[2].strip()+soup.find_all('p',class_='orange_txt')[i].contents[3].string)
            self.url_q.put(soup.select("li div h2 a")[i].get("href"))
            self.time_q.put(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        print(datetime.now().strftime('%Y-%m-%d %H:%M:%S')+" : "+"第"+str(page)+"页爬取成功")

    def add_sheet(self):
        sheet=ex.add_sheet("limundo",cell_overwrite_ok=True)
        slist=["时间","名字","价格","数据源"]
        for i in range(len(slist)):
            sheet.write(0,i,slist[i])
        for i in range(self.time_q.qsize()): 
            sheet.write(i+1,0,self.time_q.get())
            sheet.write(i+1,1,self.name_q.get())
            sheet.write(i+1,2,self.price_q.get())
            sheet.write(i+1,3,self.url_q.get())

    def get_max_page(self):
        url="https://www.limundo.com/pretragaLimundo.php?bSearchBox=1&txtPretraga="+self.query_name+"&Submit=&sSort=&sSmer=ASC"
        r=requests.get(url,headers={'UserAgent':UserAgent().random})
        max_page=BeautifulSoup(r.text,'lxml').find(attrs={"aria-label":"Last page"}).get("href").split("=")[-1]
        if max_page=='javascript:void(0)':
            max_page=1
        return max_page 

    def main(self):
        self.query_name=input("输入搜索名字：")
        print("最大页数为：",self.get_max_page())
        page_0=input("请输入你想爬取的起始页数: ")
        page_1=input("请输入你想爬取的末尾页数: ")
        pool=multiprocessing.Pool() 
        pages=range(int(page_0),int(page_1)+1)
        pool.map(self.analysis,pages)
        pool.close()
        pool.join()
        print("ojbk !!")
        self.add_sheet()




# def run():
#     '''处理主要逻辑'''
#     select=input(''' 

# ————————————————————————————————————————————————————————————————————————————————————————
# ******************************| ①www.kupujemprodajem.com |******************************
# ******************************|   ②www.verkkokauppa.com  |******************************
# ******************************|    ③www.emag.bg          |******************************
# ******************************|    ④www.ebay.com         |******************************
# ******************************|                          |******************************
# —————--不好好填数字的人都是-—————————————————————————————————————————— 蔡徐坤---————————————
#                             1.都爬(默认：bike)     2.自定义
# —————---——————————————————————————————————————————----————————————————————---————————————
#                                 你的选择是：''')
#     if select==str(1):
#         emag=EMAG()
#         emag.main(1)
#         verkkokauppa=VERKKOKAUPPA()
#         verkkokauppa.main(1)
#         ebay=EBAY()
#         ebay.main(1)
#         kupujemprodajem=KUPUJEMPRODAJEM()
#         kupujemprodajem.main(1)

#         print('已保存为 tkx.xls')
#         ex.save("tkx.xls")
        
#     elif select==str(2):
#         print('当前电脑的CPU核数是',multiprocessing.cpu_count(),'核') 
#         print("----------kupujemprodajem-----------")    
#         kupujemprodajem=KUPUJEMPRODAJEM()
#         kupujemprodajem.main(2)
#         print("---------- verkkokauppa  -----------")    
#         verkkokauppa=VERKKOKAUPPA()
#         verkkokauppa.main(2)
#         print("------------- emag  -----------")    
#         emag=EMAG()
#         emag.main(2)
#         print("------------- ebay  -----------")    
#         ebay=EBAY()
#         ebay.main(2)
#         file_name=input("为你的Excel文件起个名字吧：")
#         ex.save(file_name+".xls")
#     else:
#         print('请输入一个数字：1 or 2')

#     print("ok!！！保存完毕")

if __name__ == '__main__':









