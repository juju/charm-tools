#for $r in $relations
        cls.deployment.relate('$r[0]', '$r[1]')
#end for
