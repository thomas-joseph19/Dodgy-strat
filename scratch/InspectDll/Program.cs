using System;
using System.Reflection;
using System.Linq;

namespace InspectDll
{
    class Program
    {
        static void Main(string[] args)
        {
            var dll = @"C:\Quantower\TradingPlatform\v1.145.17\bin\TradingPlatform.PresentationLayer.dll";
            var assembly = Assembly.LoadFrom(dll);
            foreach (var type in assembly.GetExportedTypes())
            {
                if (typeof(Attribute).IsAssignableFrom(type))
                    Console.WriteLine($"{type.Namespace}.{type.Name}");
            }
        }
    }
}
