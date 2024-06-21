import asyncio
import tornado

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello, world")
    
    def put(self):
        body = json.loads(self.request.body)
        # do some stuff here
        self.write("{} your ID is {}".format(body['name'], body['id']))
        
def make_app():
    return tornado.web.Application([
        (r"/activehost", MainHandler),
    ])

async def main():
    app = make_app()
    app.listen(80)
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())