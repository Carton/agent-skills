
[x] 当前的这个 verify_cleanup.sh 脚本还不能完全保证AI 不偷懒：必须要检查大小（代码行数）减少了至少90%(这是正常清理的效果)，然后不能含有类似 "fcn.<hex_value>", "pcVar", "puVar" 等这样的字符串，才算是真正的完成清理工作。
如下面这些：
```
   4 char * fcn.000083a0(uint32_t arg1,char *arg2,int64_t arg3,int64_t arg4)
   5
   6 {
   7     unkbyte10 Var1;
   8     uint uVar2;
   9     int iVar3;
  10     int iVar4;
  11     char *pcVar5;
  12     char *pcVar6;
  13     char *pcVar7;
  14     int *piVar8;
  15     int64_t iVar9;
  16     uint64_t uVar10;
  17     int64_t *piVar11;
  18     uint *puVar12;
  ```

[x] 上下文管理，在做最后一步清理工作的时候（AI 来逐个清理函数的时候），如何有效管理上下文，是一个很大的问题。首先一般需要一个类似于函数和关键数据结构的概览，方便整体解析。但是又不能把所有东西都塞进上下文里，所以需要一个 smart 的策略来决定把什么塞进去。这块需要研究一下别的skill 是怎么做的

[ ] 怎么保证逐个处理每个文件的时候不偷懒。
[ ] 怎么尽可能的用脚本来代替md 中的不必要的描述