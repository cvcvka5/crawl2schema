import asyncio

def as_new_section_async(func):
    def inner():
        print(f"\n\n---\t{func.__name__}\t---\n")
        asyncio.run(func())
        print(f"\n---\tEND\t---")
    return inner

def as_new_section_sync(func):
    def inner():
        print(f"\n\n---\t{func.__name__}\t---\n")
        func()
        print(f"\n---\tEND\t---")
    return inner