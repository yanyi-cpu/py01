class Book:
    def __init__(self, name, stock):
        self.name = name
        self.stock = stock

    def reduce_stock(self, num):
        if self.stock >= num:
            self.stock -= num
            return True
        return False

    def add_stock(self, num):
        self.stock += num

class Member:
    def __init__(self, card_id, password):
        self.card_id = card_id
        self.password = password
        self.borrowed_books = []

    def get_max_borrow(self):
        raise NotImplementedError("子类必须实现get_max_borrow方法")

    def borrow_book(self, book: Book, num):
        max_num = self.get_max_borrow()
        current_borrowed = sum(b[1] for b in self.borrowed_books)

        if current_borrowed + num > max_num:
            print(f"借书失败！你最多只能借{max_num}本，当前已借{current_borrowed}本")
            return False
        if not book.reduce_stock(num):
            print(f"借书失败！《{book.name}》库存不足，当前库存：{book.stock}")
            return False
        self.borrowed_books.append((book.name, num))
        print(f"借书成功！已借《{book.name}》{num}本")
        return True

    def return_book(self, book: Book, num):
        for i, (name, count) in enumerate(self.borrowed_books):
            if name == book.name:
                if count >= num:
                    if count == num:
                        self.borrowed_books.pop(i)
                    else:
                        self.borrowed_books[i] = (name, count - num)
                    book.add_stock(num)
                    print(f"还书成功！归还《{book.name}》{num}本")
                    return True
                else:
                    print(f"还书失败！你只借了{count}本《{book.name}》，不能还{num}本")
                    return False
        print(f"还书失败！你没有借阅过《{book.name}》")
        return False

    def show_my_borrow(self):
        if not self.borrowed_books:
            print("你当前没有借阅任何图书")
            return
        print("=== 我的借阅列表 ===")
        for name, count in self.borrowed_books:
            print(f"《{name}》：{count}本")

class NormalMember(Member):
    def get_max_borrow(self):
        return 3


class VIPMember(Member):
    def __init__(self, card_id, password, level=1):
        super().__init__(card_id, password)
        self.level = level 
    def get_max_borrow(self):
        return 6 + self.level

class LibrarySystem:
    def __init__(self):
        self.books = [
            Book("Python入门", 10),
            Book("Java基础", 8),
            Book("数据结构", 5)
        ]
        self.members = [
            NormalMember("123456", "123456"),
            VIPMember("2479", "123456", level=6)
        ]
        self.current_user = None

    def login(self):
        """会员登录"""
        while True:
            print("\n===== 会员登录 =====")
            card_id = input("请输入会员卡号：")
            password = input("请输入密码：")
            for member in self.members:
                if member.card_id == card_id and member.password == password:
                    self.current_user = member
                    if isinstance(member, VIPMember):
                        print(f"登录成功！你是VIP{member.level}级会员")
                    else:
                        print("登录成功！你是普通会员")
                    return True
            print("卡号或密码错误！")
            choice = input("输入quit退出，按其他键重新登录：")
            if choice.lower() == "quit":
                print("退出系统")
                return False

    def show_books(self):
        print("\n===== 图书列表 =====")
        for i, book in enumerate(self.books, 1):
            print(f"{i}. 《{book.name}》 库存：{book.stock}本")

    def menu(self):
        while True:
            print("\n===== 图书管理系统 =====")
            print("1. 借书")
            print("2. 还书")
            print("3. 查看我的借阅")
            print("4. 退出系统")
            choice = input("请输入你的选择：")

            if choice == "1":
                self.show_books()
                try:
                    book_idx = int(input("请输入要借的图书编号：")) - 1
                    num = int(input("请输入要借的数量："))
                    if 0 <= book_idx < len(self.books) and num > 0:
                        self.current_user.borrow_book(self.books[book_idx], num)
                    else:
                        print("输入无效！")
                except ValueError:
                    print("请输入有效数字！")

            elif choice == "2":
                self.current_user.show_my_borrow()
                if not self.current_user.borrowed_books:
                    continue
                try:
                    book_name = input("请输入要归还的图书名称：")
                    num = int(input("请输入要归还的数量："))
                    if num > 0:
                        book = next((b for b in self.books if b.name == book_name), None)
                        if book:
                            self.current_user.return_book(book, num)
                        else:
                            print("图书不存在！")
                    else:
                        print("输入无效！")
                except ValueError:
                    print("请输入有效数字！")
            elif choice == "3":
                self.current_user.show_my_borrow()
            elif choice == "4":
                print("退出系统，欢迎下次使用！")
                break
            else:
                print("无效选项，请重新输入！")

if __name__ == "__main__":
    system = LibrarySystem()
    if system.login():
        system.menu()