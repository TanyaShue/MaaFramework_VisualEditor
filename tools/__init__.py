#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HSV颜色范围计算脚本
用于计算能识别目标图片但不识别排除图片的HSV范围
支持中文文件名和路径

示例文件名：
- 目标图片: 1_3.png
- 排除图片: 1_4.png

可通过命令行参数或修改脚本中的变量来使用其他文件名
"""

import cv2
import numpy as np
import sys
from pathlib import Path


def read_image_unicode(filepath):
    """读取包含中文路径的图片"""
    try:
        # 使用numpy读取文件，然后用OpenCV解码
        with open(filepath, 'rb') as f:
            bytes_data = f.read()
        nparr = np.frombuffer(bytes_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img
    except Exception as e:
        print(f"读取图片失败: {e}")
        return None


def save_image_unicode(filepath, img):
    """保存图片到包含中文的路径"""
    try:
        # 编码图片
        success, encoded = cv2.imencode('.jpg', img)
        if success:
            # 写入文件
            with open(filepath, 'wb') as f:
                f.write(encoded.tobytes())
            return True
    except Exception as e:
        print(f"保存图片失败: {e}")
        return False


def analyze_hsv_distribution(image, name="Image"):
    """分析图片的HSV分布"""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)

    print(f"\n{'=' * 50}")
    print(f"{name} 的HSV分析:")
    print(f"{'=' * 50}")

    # 计算各通道的统计信息
    channels = {'H': h, 'S': s, 'V': v}
    stats = {}

    for channel_name, channel_data in channels.items():
        stats[channel_name] = {
            'min': np.min(channel_data),
            'max': np.max(channel_data),
            'mean': np.mean(channel_data),
            'std': np.std(channel_data),
            'median': np.median(channel_data),
            'q1': np.percentile(channel_data, 25),
            'q3': np.percentile(channel_data, 75)
        }

        print(f"\n{channel_name}通道:")
        print(f"  最小值: {stats[channel_name]['min']}")
        print(f"  最大值: {stats[channel_name]['max']}")
        print(f"  平均值: {stats[channel_name]['mean']:.2f}")
        print(f"  标准差: {stats[channel_name]['std']:.2f}")
        print(f"  中位数: {stats[channel_name]['median']:.2f}")

    return hsv, stats


def find_optimal_range_with_threshold(target_hsv, exclude_hsv, target_stats, exclude_stats):
    """寻找最优的HSV范围和阈值"""
    print(f"\n{'=' * 50}")
    print("寻找最优HSV范围和匹配阈值...")
    print(f"{'=' * 50}")

    # 分析两张图片的HSV差异
    print(f"\n分析两张图片的差异:")
    max_diff_channel = None
    max_diff_value = 0

    for channel, idx in [('H', 0), ('S', 1), ('V', 2)]:
        target_mean = target_stats[channel]['mean']
        exclude_mean = exclude_stats[channel]['mean']
        diff = abs(target_mean - exclude_mean)
        print(f"  {channel}通道平均值差异: {diff:.2f} (目标:{target_mean:.2f}, 排除:{exclude_mean:.2f})")

        if diff > max_diff_value:
            max_diff_value = diff
            max_diff_channel = channel

    print(f"\n💡 最大差异在{max_diff_channel}通道")

    # 存储所有测试结果
    test_results = []

    # 初始化最优参数
    best_lower = None
    best_upper = None
    best_threshold = None
    best_gap = -1  # 目标和排除之间的像素数差距
    best_target_count = 0
    best_exclude_count = 0

    # 生成多个候选范围进行测试
    print("\n测试多个HSV范围组合...")

    # 策略1: 基于统计信息的范围
    ranges_to_test = []

    # 基于均值和标准差
    for std_factor in [0.5, 1.0, 1.5, 2.0, 2.5]:
        lower = np.array([
            int(max(0, target_stats['H']['mean'] - std_factor * target_stats['H']['std'])),
            int(max(0, target_stats['S']['mean'] - std_factor * target_stats['S']['std'])),
            int(max(0, target_stats['V']['mean'] - std_factor * target_stats['V']['std']))
        ], dtype=np.uint8)

        upper = np.array([
            int(min(179, target_stats['H']['mean'] + std_factor * target_stats['H']['std'])),
            int(min(255, target_stats['S']['mean'] + std_factor * target_stats['S']['std'])),
            int(min(255, target_stats['V']['mean'] + std_factor * target_stats['V']['std']))
        ], dtype=np.uint8)

        ranges_to_test.append((lower, upper, f"标准差因子{std_factor}"))

    # 基于四分位数
    lower_q = np.array([
        int(max(0, target_stats['H']['q1'])),
        int(max(0, target_stats['S']['q1'])),
        int(max(0, target_stats['V']['q1']))
    ], dtype=np.uint8)

    upper_q = np.array([
        int(min(179, target_stats['H']['q3'])),
        int(min(255, target_stats['S']['q3'])),
        int(min(255, target_stats['V']['q3']))
    ], dtype=np.uint8)

    ranges_to_test.append((lower_q, upper_q, "四分位数范围"))

    # 特别针对V通道优化（如果V通道差异大）
    v_diff = abs(target_stats['V']['mean'] - exclude_stats['V']['mean'])
    if v_diff > 20:
        # 创建几个专注于V通道的范围
        for v_factor in [0.5, 1.0, 1.5]:
            lower_v = np.array([
                int(max(0, target_stats['H']['mean'] - 2 * target_stats['H']['std'])),
                int(max(0, target_stats['S']['mean'] - 2 * target_stats['S']['std'])),
                int(max(0, target_stats['V']['mean'] - v_factor * target_stats['V']['std']))
            ], dtype=np.uint8)

            upper_v = np.array([
                int(min(179, target_stats['H']['mean'] + 2 * target_stats['H']['std'])),
                int(min(255, target_stats['S']['mean'] + 2 * target_stats['S']['std'])),
                int(min(255, target_stats['V']['mean'] + v_factor * target_stats['V']['std']))
            ], dtype=np.uint8)

            # 如果目标比排除暗，限制V上界
            if target_stats['V']['mean'] < exclude_stats['V']['mean']:
                upper_v[2] = int(min(upper_v[2],
                                     (target_stats['V']['mean'] + exclude_stats['V']['mean']) / 2))
            else:
                lower_v[2] = int(max(lower_v[2],
                                     (target_stats['V']['mean'] + exclude_stats['V']['mean']) / 2))

            ranges_to_test.append((lower_v, upper_v, f"V通道优化{v_factor}"))

    # 测试所有范围
    print(f"\n共测试{len(ranges_to_test)}个范围组合")

    for idx, (lower, upper, desc) in enumerate(ranges_to_test):
        # 确保范围有效
        valid_range = True
        for i in range(3):
            if lower[i] >= upper[i]:
                valid_range = False
                break

        if not valid_range:
            continue

        # 创建掩码并计算匹配像素数
        target_mask = cv2.inRange(target_hsv, lower, upper)
        exclude_mask = cv2.inRange(exclude_hsv, lower, upper)

        target_count = np.sum(target_mask > 0)
        exclude_count = np.sum(exclude_mask > 0)

        # 记录结果
        test_results.append({
            'lower': lower.copy(),
            'upper': upper.copy(),
            'target_count': target_count,
            'exclude_count': exclude_count,
            'desc': desc
        })

        # 寻找最大化目标和排除之间差距的范围
        gap = target_count - exclude_count

        # 只有当目标数量大于排除数量时才考虑
        if target_count > exclude_count and target_count > 100:  # 至少要有100个像素
            if gap > best_gap:
                best_gap = gap
                best_lower = lower.copy()
                best_upper = upper.copy()
                best_target_count = target_count
                best_exclude_count = exclude_count

    # 如果没有找到理想的范围（目标>排除），则寻找折中方案
    if best_lower is None:
        print("\n⚠️ 未找到目标数量大于排除数量的范围，寻找最佳折中方案...")

        # 找出目标数量最多且排除数量相对较少的范围
        best_score = -float('inf')
        for result in test_results:
            if result['target_count'] > 50:  # 至少要识别一些像素
                score = result['target_count'] - 1.5 * result['exclude_count']
                if score > best_score:
                    best_score = score
                    best_lower = result['lower']
                    best_upper = result['upper']
                    best_target_count = result['target_count']
                    best_exclude_count = result['exclude_count']

    # 计算最佳阈值
    if best_lower is not None:
        # 阈值设置在两者之间，偏向确保不识别排除图片
        if best_exclude_count < best_target_count:
            # 理想情况：排除数量 < 目标数量
            # 阈值设置为排除数量 + (差值的20%)
            threshold = int(best_exclude_count + 0.2 * (best_target_count - best_exclude_count))
            # 确保阈值高于排除数量
            threshold = max(threshold, best_exclude_count + 10)
        else:
            # 非理想情况：使用更保守的策略
            threshold = int(best_target_count * 0.8)

        # 确保阈值合理
        threshold = max(threshold, 50)  # 至少50个像素
        threshold = min(threshold, best_target_count - 10)  # 确保能识别目标

        best_threshold = threshold

    # 显示所有测试结果的摘要
    print(f"\n测试结果摘要（显示前10个）:")
    print(f"{'描述':20} {'目标像素数':>10} {'排除像素数':>10} {'差值':>10}")
    print("-" * 54)

    # 按目标像素数排序
    test_results.sort(key=lambda x: x['target_count'] - x['exclude_count'], reverse=True)

    for i, result in enumerate(test_results[:10]):
        gap = result['target_count'] - result['exclude_count']
        print(f"{result['desc']:20} {result['target_count']:>10} {result['exclude_count']:>10} {gap:>10}")

    return best_lower, best_upper, best_threshold, best_target_count, best_exclude_count


def visualize_results(target_img, exclude_img, lower, upper, threshold=None, target_count=None, exclude_count=None):
    """可视化结果"""
    # 创建掩码
    target_hsv = cv2.cvtColor(target_img, cv2.COLOR_BGR2HSV)
    exclude_hsv = cv2.cvtColor(exclude_img, cv2.COLOR_BGR2HSV)

    target_mask = cv2.inRange(target_hsv, lower, upper)
    exclude_mask = cv2.inRange(exclude_hsv, lower, upper)

    # 如果没有提供计数，则计算
    if target_count is None:
        target_count = np.sum(target_mask > 0)
    if exclude_count is None:
        exclude_count = np.sum(exclude_mask > 0)

    # 应用掩码
    target_result = cv2.bitwise_and(target_img, target_img, mask=target_mask)
    exclude_result = cv2.bitwise_and(exclude_img, exclude_img, mask=exclude_mask)

    # 为小图片添加放大功能
    scale = 1
    if target_img.shape[0] < 100 or target_img.shape[1] < 100:
        scale = max(3, min(10, 300 // max(target_img.shape[0], target_img.shape[1])))
        print(f"\n检测到小尺寸图片，放大{scale}倍显示")

        target_img = cv2.resize(target_img, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
        target_result = cv2.resize(target_result, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
        target_mask_vis = cv2.resize(target_mask, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)

        exclude_img = cv2.resize(exclude_img, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
        exclude_result = cv2.resize(exclude_result, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
        exclude_mask_vis = cv2.resize(exclude_mask, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
    else:
        target_mask_vis = target_mask
        exclude_mask_vis = exclude_mask

    # 将掩码转换为三通道用于显示
    target_mask_bgr = cv2.cvtColor(target_mask_vis, cv2.COLOR_GRAY2BGR)
    exclude_mask_bgr = cv2.cvtColor(exclude_mask_vis, cv2.COLOR_GRAY2BGR)

    # 创建显示图像（原图 | 掩码 | 结果）
    target_display = np.hstack([target_img, target_mask_bgr, target_result])
    exclude_display = np.hstack([exclude_img, exclude_mask_bgr, exclude_result])

    # 添加文字标签
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.5 * scale
    thickness = max(1, scale // 2)

    # 目标图片标签
    cv2.putText(target_display, "Original", (10, 20 * scale), font, font_scale, (0, 255, 0), thickness)
    cv2.putText(target_display, "Mask", (target_img.shape[1] + 10, 20 * scale), font, font_scale, (0, 255, 0),
                thickness)
    cv2.putText(target_display, "Result", (target_img.shape[1] * 2 + 10, 20 * scale), font, font_scale, (0, 255, 0),
                thickness)

    # 添加匹配像素数信息
    count_text = f"Count: {target_count}"
    if threshold is not None:
        if target_count >= threshold:
            count_text += f" >= {threshold} (MATCH)"
            color = (0, 255, 0)  # 绿色
        else:
            count_text += f" < {threshold} (NO MATCH)"
            color = (0, 0, 255)  # 红色
    else:
        color = (0, 255, 0)
    cv2.putText(target_display, count_text, (10, 40 * scale), font, font_scale, color, thickness)

    # 排除图片标签
    cv2.putText(exclude_display, "Original", (10, 20 * scale), font, font_scale, (0, 0, 255), thickness)
    cv2.putText(exclude_display, "Mask", (exclude_img.shape[1] + 10, 20 * scale), font, font_scale, (0, 0, 255),
                thickness)
    cv2.putText(exclude_display, "Result", (exclude_img.shape[1] * 2 + 10, 20 * scale), font, font_scale, (0, 0, 255),
                thickness)

    # 添加匹配像素数信息
    count_text = f"Count: {exclude_count}"
    if threshold is not None:
        if exclude_count >= threshold:
            count_text += f" >= {threshold} (MATCH)"
            color = (0, 0, 255)  # 红色（不应该匹配）
        else:
            count_text += f" < {threshold} (NO MATCH)"
            color = (0, 255, 0)  # 绿色（正确）
    else:
        color = (0, 0, 255)
    cv2.putText(exclude_display, count_text, (10, 40 * scale), font, font_scale, color, thickness)

    return target_display, exclude_display


def main():
    # 设置图片路径
    try:
        script_dir = Path(__file__).parent
    except:
        # 如果__file__不可用，使用当前工作目录
        script_dir = Path.cwd()

    # 你可以修改这两个文件名
    target_image_name = "通用_2.png"  # 需要识别的图片
    exclude_image_name = "通用_3.png"  # 不需要识别的图片

    # 或者使用命令行参数
    if len(sys.argv) >= 3:
        target_image_name = sys.argv[1]
        exclude_image_name = sys.argv[2]
        print(f"使用命令行参数指定的文件: {target_image_name}, {exclude_image_name}")

    target_path = script_dir / target_image_name
    exclude_path = script_dir / exclude_image_name

    print("\nHSV颜色范围计算工具")
    print("=" * 50)
    print(f"脚本路径: {script_dir}")
    print(f"目标图片: {target_image_name}")
    print(f"排除图片: {exclude_image_name}")
    print(f"完整路径:")
    print(f"  - {target_path}")
    print(f"  - {exclude_path}")

    # 检查文件是否存在
    if not target_path.exists():
        print(f"\n错误: 找不到目标图片 '{target_image_name}'")
        print(f"请确保图片文件在脚本同一目录下: {script_dir}")
        print("\n当前目录中的图片文件:")
        for f in script_dir.glob("*.png"):
            print(f"  - {f.name}")
        for f in script_dir.glob("*.jpg"):
            print(f"  - {f.name}")
        sys.exit(1)

    if not exclude_path.exists():
        print(f"\n错误: 找不到排除图片 '{exclude_image_name}'")
        print(f"请确保图片文件在脚本同一目录下: {script_dir}")
        print("\n当前目录中的图片文件:")
        for f in script_dir.glob("*.png"):
            print(f"  - {f.name}")
        for f in script_dir.glob("*.jpg"):
            print(f"  - {f.name}")
        sys.exit(1)

    # 读取图片（支持中文路径）
    target_img = read_image_unicode(str(target_path))
    exclude_img = read_image_unicode(str(exclude_path))

    if target_img is None:
        print(f"\n错误: 无法读取目标图片 '{target_image_name}'")
        print("请检查文件是否存在或文件格式是否正确")
        sys.exit(1)

    if exclude_img is None:
        print(f"\n错误: 无法读取排除图片 '{exclude_image_name}'")
        print("请检查文件是否存在或文件格式是否正确")
        sys.exit(1)

    print(f"\n成功读取图片:")
    print(f"  目标图片尺寸: {target_img.shape}")
    print(f"  排除图片尺寸: {exclude_img.shape}")

    # 分析HSV分布
    target_hsv, target_stats = analyze_hsv_distribution(target_img, "目标图片")
    exclude_hsv, exclude_stats = analyze_hsv_distribution(exclude_img, "排除图片")

    # 寻找最优范围和阈值
    lower, upper, threshold, target_count, exclude_count = find_optimal_range_with_threshold(
        target_hsv, exclude_hsv, target_stats, exclude_stats
    )

    # 输出最终结果
    print(f"\n{'=' * 50}")
    print("最终推荐的HSV范围和阈值:")
    print(f"{'=' * 50}")
    print(f"\n🎯 HSV范围:")
    print(f"lower = np.array([{lower[0]}, {lower[1]}, {lower[2]}])")
    print(f"upper = np.array([{upper[0]}, {upper[1]}, {upper[2]}])")

    print(f"\n📊 匹配像素统计:")
    print(f"  目标图片匹配像素数: {target_count} 个")
    print(f"  排除图片匹配像素数: {exclude_count} 个")
    print(
        f"  总像素数: 目标图片={target_hsv.shape[0] * target_hsv.shape[1]}个, 排除图片={exclude_hsv.shape[0] * exclude_hsv.shape[1]}个")

    print(f"\n✅ 推荐阈值: {threshold} 个像素")
    print(f"  - 当匹配像素数 >= {threshold} 时，判定为【识别到目标】")
    print(f"  - 当匹配像素数 < {threshold} 时，判定为【未识别到】")

    # 验证阈值效果
    print(f"\n🔍 阈值验证:")
    if target_count >= threshold:
        print(f"  ✓ 目标图片 ({target_count}) >= 阈值 ({threshold}) → 正确识别")
    else:
        print(f"  ✗ 目标图片 ({target_count}) < 阈值 ({threshold}) → 错误！需要调整")

    if exclude_count < threshold:
        print(f"  ✓ 排除图片 ({exclude_count}) < 阈值 ({threshold}) → 正确排除")
    else:
        print(f"  ✗ 排除图片 ({exclude_count}) >= 阈值 ({threshold}) → 错误！需要调整")

    # 安全边界检查
    safety_margin = threshold - exclude_count
    if safety_margin < 20:
        print(f"\n⚠️  警告: 安全边界较小 ({safety_margin}像素)")
        print("   建议: 考虑使用更严格的阈值或其他识别方法")

    # 特别提示
    h_diff = abs(target_stats['H']['mean'] - exclude_stats['H']['mean'])
    s_diff = abs(target_stats['S']['mean'] - exclude_stats['S']['mean'])
    v_diff = abs(target_stats['V']['mean'] - exclude_stats['V']['mean'])

    if v_diff > h_diff and v_diff > s_diff and v_diff > 20:
        print(f"\n📌 特别提示: V通道（明度）差异最大({v_diff:.1f})")
        print(f"   目标图片V值主要范围: {lower[2]}-{upper[2]}")

    # 可视化结果
    print("\n正在生成可视化结果...")
    target_display, exclude_display = visualize_results(
        target_img, exclude_img, lower, upper, threshold, target_count, exclude_count
    )

    # 保存结果（支持中文路径）
    save_image_unicode(str(script_dir / "result_target.jpg"), target_display)
    save_image_unicode(str(script_dir / "result_exclude.jpg"), exclude_display)
    print(f"\n可视化结果已保存:")
    print(f"  - result_target.jpg")
    print(f"  - result_exclude.jpg")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断程序")
        cv2.destroyAllWindows()
    except OverflowError as e:
        print(f"\n程序出错: {e}")
        print("这通常是由于数值溢出导致的，请检查图片数据")
        cv2.destroyAllWindows()
    except Exception as e:
        print(f"\n程序出错: {e}")
        import traceback

        traceback.print_exc()
        cv2.destroyAllWindows()