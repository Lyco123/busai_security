#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CAN数据解压缩工具
将JavaScript的WebAssembly解密脚本移植到Python

使用方法:
    python decrypt_tool.py --wasm <wasm文件路径> --obuid <OBUID> --base64 <base64数据>

依赖安装:
    pip install wasmtime

示例:
    python decrypt_tool.py \\
        --wasm "js解压缩及demo说明/libCompress.wasm" \\
        --obuid "UUUU" \\
        --base64 "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"
"""

import os
import sys
import json
from typing import Optional
import traceback

try:
    import wasmtime
    from wasmtime import Store, Module, Instance, Func, Memory, MemoryType, ValType, Limits, FuncType, Table, TableType, \
    Engine
except ImportError:
    print("错误: 需要安装 wasmtime 库")
    print("请运行: pip install wasmtime")
    sys.exit(1)


class CanDataDecryptor:
    """CAN数据解密器"""

    def __init__(self, wasm_path: str):
        """
        初始化解密器

        Args:
            wasm_path: libCompress.wasm 文件路径
        """
        if not os.path.exists(wasm_path):
            raise FileNotFoundError(f"WASM文件不存在: {wasm_path}")


        self.store = Store()
        self.wasm_path = wasm_path
        self.module = None
        self.instance = None
        self.memory = None
        self.handle = None
        self.table = None


        # 内存指针
        self.pObuidArrayBufer = None;
        self.pBase64ArrayBufer = None;
        self.pOutJsonArrayBufer = None;
        self.pObuidPtr = None;
        self.pBase64Ptr = None;
        self.pOutJsonPtr = None;
        self.bInitSuccess = False;
        self.pHandle = None;


        # 内存大小
        self.OBUID_SIZE = 1024
        self.BASE64_SIZE = 1024 * 1024 * 2
        self.OUT_JSON_SIZE = 1024 * 1024 * 8
        self.pointers = {}  # 添加缺失的pointers属性

        self._load_wasm()
        self._init_memory()

    def _load_wasm(self):
        """加载WASM模块"""
        try:
            with open(self.wasm_path, 'rb') as f:
                wasm_bytes = f.read()

            self.module = Module(self.store.engine, wasm_bytes)

            # 创建 Limits 实例
            limits = Limits(min=1600, max=1600)

            # 传递实例给 MemoryType
            memory_type = MemoryType(limits=limits)

            memory = Memory(self.store, memory_type)


            imports = [
                (Func(self.store, FuncType([ValType.i32()], [ValType.i32()]),self._time,True)),  # 修正参数类型
                (Func(self.store, FuncType([ValType.i32(), ValType.i32(),ValType.i32()], []), self._cxa_throw,True)),  # 无参数无返回值
                (Func(self.store, FuncType([ValType.i32()], [ValType.i32()]), self._cxa_allocate_exception,True)),  # 修正参数类型
                (Func(self.store, FuncType([ValType.i32(), ValType.i32(),ValType.i32(),ValType.i32()], [ValType.i32()]), self._fd_write,True)),
                # 修正参数数量
                (Func(self.store, FuncType([], []),self._abort,True)),  # 无参数无返回值
                (Func(self.store, FuncType([ValType.i32(),ValType.i32()], [ValType.i32()]),self._pthread_join,True)),  # 修正参数类型
                (Func(self.store,FuncType([ValType.i32(), ValType.i32(), ValType.i32(), ValType.i32(),ValType.i32()], [ValType.i32()]),
                        self._strftime_l,True)),  # 修正参数类型
                (Func(self.store, FuncType([ValType.i32(), ValType.i32()], [ValType.i32()]), self._environ_get,True)),
                # 修正参数类型
                (Func(self.store, FuncType([ValType.i32(), ValType.i32()], [ValType.i32()]),self._environ_sizes_get,True)),
                # 修正参数类型
                (Func(self.store, FuncType([ValType.i32(), ValType.i32(), ValType.i32()], [ValType.i32()]),self._emscripten_memcpy_big,True)),
                # 修正参数类型
                (Func(self.store, FuncType([ValType.i32()], [ValType.i32()]),self._emscripten_resize_heap,True))  # 修正参数类型
                # (memory)
            ]
            self.instance = Instance(self.store, self.module, imports)
            self.memory = memory


            # 获取导出函数
            exports = self.instance.exports(self.store)
            for name, obj in exports.items():
                print(f"{name}: {type(obj)}")  # 输出名称和类型
            self._wasm_call_ctors = exports['m']
            self._create = exports['n']
            self._uncompress = exports['o']
            self._delete_ptr = exports['p']
            self._malloc = exports.get('q')
            self._free = exports.get('r')

            # 分配内存
            self._allocate_memory()

            # 初始化构造函数
            self._wasm_call_ctors(self.store)

        except Exception as e:
            raise RuntimeError(f"加载WASM模块失败: {e}")

    def _allocate_memory(self):
        """分配必要的内存空间"""
        if not self._malloc:
            raise RuntimeError("未找到malloc函数")

        # 分配OBUID内存
        self.p_obuid_ptr = self._malloc(self.store, self.OBUID_SIZE)
        # 分配Base64内存
        self.p_base64_ptr = self._malloc(self.store, self.BASE64_SIZE)
        # 分配输出JSON内存
        self.p_out_json_ptr = self._malloc(self.store, self.OUT_JSON_SIZE)

        # 保存指针以便释放
        self.pointers = {
            'obuid': self.p_obuid_ptr,
            'base64': self.p_base64_ptr,
            'json': self.p_out_json_ptr
        }

    def _init_memory(self):
        """初始化内存指针"""
        # 分配内存
        self.p_obuid_ptr = self._malloc(self.store, self.OBUID_SIZE)
        self.p_base64_ptr = self._malloc(self.store, self.BASE64_SIZE)
        self.p_out_json_ptr = self._malloc(self.store, self.OUT_JSON_SIZE)
        # 创建handle
        self.handle = self._create(self.store)

    def _write_string_to_memory(self, ptr: int, data: bytes):
        """将字符串写入WASM内存"""
        memory_data = self.memory.data_ptr(self.store)
        memory_size = self.memory.size(self.store) * 65536  # 计算内存大小（页数*64KB）

        if ptr + len(data) > memory_size:
            raise RuntimeError("内存写入越界")

        for i, byte_val in enumerate(data):
            memory_data[ptr + i] = byte_val

        # 添加null终止符
        if ptr + len(data) < memory_size:
            memory_data[ptr + len(data)] = 0

    def _read_string_from_memory(self, ptr: int, length: int) -> bytes:
        """从WASM内存读取字符串"""
        memory_data = self.memory.data_ptr(self.store)
        memory_size = self.memory.size(self.store)* 65536

        if ptr + length > memory_size:
            raise RuntimeError("内存读取越界")

        data_buffer=bytes(memory_data[ptr:ptr + length])

        return data_buffer


    def uncompress_can_data_to_json(self, obuid: str, base64_data: str) -> Optional[str]:
        try:
            # 编码字符串
            obuid_bytes = obuid.encode('utf-8')
            base64_bytes = base64_data.encode('utf-8')

            # 检查大小
            if len(obuid_bytes) >= self.OBUID_SIZE:
                raise ValueError(f"OBUID太长，最大 {self.OBUID_SIZE} 字节")
            if len(base64_bytes) >= self.BASE64_SIZE:
                raise ValueError(f"Base64数据太长，最大 {self.BASE64_SIZE} 字节")

            # 写入内存
            self._write_string_to_memory(self.p_obuid_ptr, obuid_bytes)
            self._write_string_to_memory(self.p_base64_ptr, base64_bytes)

            ccc=self._read_string_from_memory(self.p_obuid_ptr, len(obuid_bytes))

            ddd = self._read_string_from_memory(self.p_base64_ptr, len(base64_bytes))

            # 调用解压函数
            result_length = self._uncompress(
                self.store,
                self.handle,
                self.p_obuid_ptr,
                self.p_base64_ptr,
                self.p_out_json_ptr,
                self.OUT_JSON_SIZE
            )

            if result_length == 0:
                return None

            # 读取结果
            result_bytes = self._read_string_from_memory(self.p_out_json_ptr, result_length)
            return result_bytes.decode('utf-8')

        except Exception as e:
            print(f"解压失败: {e}", file=sys.stderr)
            traceback.print_exc()
            return None

    def __del__(self):
        """清理资源"""
        if hasattr(self, 'handle') and self.handle is not None:
            try:
                self._delete_ptr(self.store, self.handle)
            except:
                pass

    # WASM导入函数实现
    def _time(self, caller, ptr: int) -> int:
        """时间函数"""
        import time
        timestamp = int(time.time())
        if ptr != 0:
            memory_data = self.memory.data(caller)
            # 写入32位整数（小端序）
            for i in range(4):
                if ptr + i < len(memory_data):
                    memory_data[ptr + i] = (timestamp >> (i * 8)) & 0xFF
        return timestamp

    def _cxa_throw(self, caller, ptr: int, type_ptr: int, destructor: int):
        """异常抛出函数"""
        raise RuntimeError("WASM异常")

    def _cxa_allocate_exception(self, caller, size: int) -> int:
        """分配异常内存"""
        return self._malloc(caller, size + 16) + 16

    def _fd_write(self, caller, fd: int, iov: int, iovcnt: int, pnum: int) -> int:
        """文件写入函数"""
        memory_data = self.memory.data(caller)
        total = 0
        for i in range(iovcnt):
            # 读取指针和长度（每个iov是8字节：4字节ptr + 4字节len）
            ptr_bytes = bytes(memory_data[iov + i * 8:iov + i * 8 + 4])
            len_bytes = bytes(memory_data[iov + i * 8 + 4:iov + i * 8 + 8])
            ptr = int.from_bytes(ptr_bytes, 'little', signed=False)
            length = int.from_bytes(len_bytes, 'little', signed=False)

            data = bytes(memory_data[ptr:ptr + length])
            if fd == 1:
                sys.stdout.buffer.write(data)
            else:
                sys.stderr.buffer.write(data)
            total += length
        # 写入总长度
        for i in range(4):
            if pnum + i < len(memory_data):
                memory_data[pnum + i] = (total >> (i * 8)) & 0xFF
        return 0

    def _abort(self, store):
        """中止函数"""
        raise RuntimeError("WASM abort")

    def _pthread_join(self, caller, thread: int) -> int:
        """线程join函数"""
        return 28  # ENOSYS

    def _strftime_l(self, caller, s: int, maxsize: int, format_ptr: int, tm: int) -> int:
        """时间格式化函数"""
        # 简化实现，返回0表示失败
        return 0

    def _environ_get(self, caller, environ: int, environ_buf: int) -> int:
        """获取环境变量"""
        return 0

    def _environ_sizes_get(self, caller, penviron_count: int, penviron_buf_size: int) -> int:
        """获取环境变量大小"""
        memory_data = self.memory.read(caller)
        # 写入0
        for i in range(4):
            if penviron_count + i < len(memory_data):
                memory_data[penviron_count + i] = 0
            if penviron_buf_size + i < len(memory_data):
                memory_data[penviron_buf_size + i] = 0
        return 0

    def _emscripten_memcpy_big(self, caller, dest: int, src: int, num: int):
        """内存拷贝函数"""
        memory_data = self.memory.data(caller)
        for i in range(num):
            if dest + i < len(memory_data) and src + i < len(memory_data):
                memory_data[dest + i] = memory_data[src + i]

    def _emscripten_resize_heap(self, caller, requested_size: int) -> int:
        """调整堆大小"""
        return 0  # 不支持扩展

    def read_can_data_from_file(self, file_path):
        """
        从文件读取CAN数据
        :param file_path: 文件路径
        :return: 文件内容
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        except Exception as e:
            raise Exception(f"读取文件失败: {str(e)}")


def main():
    """主函数"""
    import argparse


    parser = argparse.ArgumentParser(
        description='CAN数据解压缩工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('--wasm', type=str,
                        default='libCompress.wasm',
                        help='WASM文件路径 (默认: js解压缩及demo说明/libCompress.wasm)')
    parser.add_argument('--obuid', type=str,help='OBU ID')
    parser.add_argument('--base64', type=str, help='Base64编码的压缩数据')
    parser.add_argument('--output', type=str,
                        help='输出JSON文件路径（可选）')

    args = parser.parse_args()

    try:
        # 创建解密器
        print(f"正在加载WASM模块: {args.wasm}")
        decryptor = CanDataDecryptor(args.wasm)
        print("WASM模块加载成功")

        # 解压数据
        args.obuid = '944795'
        args.base64 = "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"

        print(f"正在解压数据 (OBUID: {args.obuid})...")
        result = decryptor.uncompress_can_data_to_json(args.obuid, args.base64)

        if result is None:
            print("解压失败", file=sys.stderr)
            sys.exit(1)

        # 输出结果
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(result)
            print(f"结果已保存到: {args.output}")
        else:
            # 尝试格式化JSON
            try:
                json_obj = json.loads(result)
                print(json.dumps(json_obj, indent=2, ensure_ascii=False))
            except:
                print(result)

    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
