using System;
using System.Reflection;
using System.Linq;

public class Program
{
    public static void Main(string[] args)
    {
        string dllPath = args[0];
        try
        {
            var assembly = Assembly.LoadFrom(dllPath);
            var types = assembly.GetTypes();
            foreach (var type in types.Where(t => t.Name.Contains("Strategy")))
            {
                Console.WriteLine($"{type.Namespace}.{type.Name}");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error loading {dllPath}: {ex.Message}");
        }
    }
}
